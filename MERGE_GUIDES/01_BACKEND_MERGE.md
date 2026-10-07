# 01 — Backend merge

## A. Add the two new backend files
Upload/copy:

- `backend/app/v210.py`
- `backend/app/call_state_guard_v210.py`

## B. Register the V2.10 router in `backend/app/main.py`

Near your other router imports, add:

```python
from .v210 import router as v210_router
```

After `app = FastAPI(...)` and after your normal middleware/routes are created, add once:

```python
app.include_router(v210_router)
```

Do not create a second FastAPI app.

## C. Environment variables
V2.10 Q Predict analysis reuses the same Anthropic/Tavily direction already used by LEMMIQ Q/Trust.

Ensure Render has:

```text
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=<the same working model your current LEMMIQ Q uses>
TAVILY_API_KEY=...     # optional but recommended for current context
```

Optional rate setting:

```text
LEMMIQ_V210_Q_RATE_PER_MINUTE=12
```

If `TAVILY_API_KEY` is absent, `Q · Analyse this market` still works but only analyses the market data supplied by the app.

## D. Test the new backend route after deployment

Open:

```text
https://YOUR-RENDER-DOMAIN/v210/version
```

Expected:

```json
{"version":"2.10.0","name":"LEMMIQ V2.10"}
```

Then Q Predict can POST to:

```text
POST /v210/q-predict/analyse
```

## E. Do not expose a second Q provider stack
The additive endpoint is intentionally separate so the V2.9 Q flow is not broken. Once V2.10 is stable, you can later move the analysis prompt into the existing `chat_agent.py` pipeline and keep the same browser contract.
