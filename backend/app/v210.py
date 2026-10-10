from __future__ import annotations

import asyncio
import json
import os
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v210", tags=["LEMMIQ v2.10"])

VERSION = "2.10.6"


class MarketAnalyseRequest(BaseModel):
    market_id: Optional[str] = Field(default=None, max_length=100)
    question: str = Field(min_length=3, max_length=700)
    yes_percent: Optional[float] = Field(default=None, ge=0, le=100)
    no_percent: Optional[float] = Field(default=None, ge=0, le=100)
    yes_pool_pc: Optional[float] = Field(default=None, ge=0)
    no_pool_pc: Optional[float] = Field(default=None, ge=0)
    predictor_count: Optional[int] = Field(default=None, ge=0)
    close_time: Optional[str] = Field(default=None, max_length=120)
    resolution_rule: Optional[str] = Field(default=None, max_length=1500)
    resolution_source: Optional[str] = Field(default=None, max_length=300)
    user_position: Optional[str] = Field(default=None, max_length=200)
    visible_context: Optional[str] = Field(default=None, max_length=3500)


class MarketAnalyseResponse(BaseModel):
    version: str
    analysis: str
    used_live_context: bool
    live_sources: List[Dict[str, str]]
    disclaimer: str


# Small in-memory abuse guard for the additive v2.10 endpoint.
# It is intentionally conservative and should be replaced by the app's normal
# authenticated/rate-limited Q pipeline once wired into the main auth layer.
_RATE_BUCKETS: Dict[str, deque] = defaultdict(deque)
_RATE_LOCK = asyncio.Lock()
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_REQUESTS = int(os.getenv("LEMMIQ_V210_Q_RATE_PER_MINUTE", "12"))


async def _enforce_same_origin_and_rate_limit(request: Request) -> None:
    origin = request.headers.get("origin")
    host = request.headers.get("host")
    if origin and host:
        origin_host = urlparse(origin).netloc
        if origin_host and origin_host != host:
            raise HTTPException(status_code=403, detail="Cross-origin request blocked")

    forwarded = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded.split(",")[0].strip() if forwarded else ""
    if not client_ip and request.client:
        client_ip = request.client.host
    key = client_ip or "unknown"

    now = time.monotonic()
    async with _RATE_LOCK:
        bucket = _RATE_BUCKETS[key]
        while bucket and now - bucket[0] > _RATE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= _RATE_MAX_REQUESTS:
            raise HTTPException(status_code=429, detail="Q Analyse rate limit reached. Try again shortly.")
        bucket.append(now)


async def _tavily_market_context(question: str) -> tuple[str, List[Dict[str, str]]]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return "", []

    payload = {
        "api_key": api_key,
        "query": question,
        "search_depth": "advanced",
        "max_results": 5,
        "include_answer": False,
        "include_raw_content": False,
    }

    try:
        async with httpx.AsyncClient(timeout=14.0) as client:
            resp = await client.post("https://api.tavily.com/search", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return "", []

    sources: List[Dict[str, str]] = []
    chunks: List[str] = []
    for item in data.get("results", [])[:5]:
        title = str(item.get("title") or "Source").strip()
        url = str(item.get("url") or "").strip()
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        content = content[:1400]
        chunks.append(f"- {title}\n  {content}\n  URL: {url}")
        if url:
            sources.append({"title": title[:180], "url": url[:800]})
    return "\n".join(chunks), sources


def _market_prompt(body: MarketAnalyseRequest, live_context: str) -> str:
    data = {
        "question": body.question,
        "yes_percent": body.yes_percent,
        "no_percent": body.no_percent,
        "yes_pool_pc": body.yes_pool_pc,
        "no_pool_pc": body.no_pool_pc,
        "predictor_count": body.predictor_count,
        "close_time": body.close_time,
        "resolution_rule": body.resolution_rule,
        "resolution_source": body.resolution_source,
        "user_position": body.user_position,
        "visible_context": body.visible_context,
    }
    clean = {k: v for k, v in data.items() if v not in (None, "")}

    live = live_context if live_context else "No live web context was available. Analyse only the supplied market data."

    return f"""
You are Q inside LEMMIQ Q Predict. Analyse a prediction market clearly and neutrally.

MARKET DATA:
{json.dumps(clean, ensure_ascii=False, indent=2)}

OPTIONAL CURRENT CONTEXT:
{live}

Return a concise in-app analysis with these headings:
1. What this market is asking
2. Evidence for YES
3. Evidence for NO
4. What matters before resolution
5. Q view

Rules:
- Do not pretend the market percentages are objective probabilities. They are crowd/pool sentiment unless explicitly stated otherwise.
- Do not guarantee an outcome.
- Mention uncertainty and data limitations.
- Respect the supplied resolution rule/source as the authoritative settlement mechanism.
- If live context conflicts with the resolution rule, explain the conflict but do not override the rule.
- If the market has zero/few predictors, say crowd sentiment is not meaningful yet.
- If user_position is present, never encourage doubling down. Keep analysis neutral.
- Keep the whole response useful on a phone screen, ideally 250-450 words.
""".strip()


async def _anthropic_analyse(prompt: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    model = os.getenv("ANTHROPIC_MODEL", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured")
    if not model:
        raise HTTPException(status_code=503, detail="ANTHROPIC_MODEL is not configured")

    payload = {
        "model": model,
        "max_tokens": 900,
        "temperature": 0.2,
        "system": (
            "You are LEMMIQ Q, the in-app assistant. Be factual, compact, neutral and transparent. "
            "Q Predict uses the user's LEMMIQ Q wallet when staking is enabled. Q analysis never settles a market and never guarantees an outcome."
        ),
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"Q provider error ({resp.status_code})")
            data = resp.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Q provider unavailable: {type(exc).__name__}") from exc

    parts: List[str] = []
    for block in data.get("content", []):
        if block.get("type") == "text" and block.get("text"):
            parts.append(str(block["text"]).strip())
    answer = "\n\n".join(p for p in parts if p)
    if not answer:
        raise HTTPException(status_code=502, detail="Q returned an empty analysis")
    return answer


@router.get("/version")
async def v210_version() -> Dict[str, str]:
    return {"version": VERSION, "name": "LEMMIQ V2.10"}


@router.post("/q-predict/analyse", response_model=MarketAnalyseResponse)
async def analyse_q_predict_market(body: MarketAnalyseRequest, request: Request) -> MarketAnalyseResponse:
    await _enforce_same_origin_and_rate_limit(request)

    live_context, sources = await _tavily_market_context(body.question)
    prompt = _market_prompt(body, live_context)
    answer = await _anthropic_analyse(prompt)

    return MarketAnalyseResponse(
        version=VERSION,
        analysis=answer,
        used_live_context=bool(live_context),
        live_sources=sources,
        disclaimer=(
            "Q analysis is informational. Q does not control settlement or guarantee an outcome; "
            "the market's published resolution rule and source remain authoritative."
        ),
    )
