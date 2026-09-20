# LEMMIQ Trust V1.1

## Text verification
Tap `Fact / Scam Check` under an incoming message.

Pipeline: message → scam/link heuristics → Tavily web evidence (optional) → Claude evidence synthesis → status/confidence/sources.

## Render
Add `TAVILY_API_KEY` and `ANTHROPIC_API_KEY` as secret environment variables.

## Media
Do not market visual AI-detection as proof. Production media checks should combine C2PA/Content Credentials, original-source lookup, metadata, manipulation forensics and detector signals.
