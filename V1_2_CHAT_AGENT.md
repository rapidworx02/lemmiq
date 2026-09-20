# LEMMIQ V1.2 Chat Agent

## Architecture

All recent user conversations
→ bounded recent-message index
→ personal communication profile
→ Q Chat Agent
→ brief / search / summaries / suggestions

## Current scope

The agent uses up to 30 days of recent history by default and caps the amount of history sent to the AI.

It can:
- identify chats where the latest message is incoming
- create a daily brief
- answer questions grounded in recent messages
- search exact message text
- summarise individual conversations
- analyse writing style without inferring sensitive personal traits

## Important

This V1.2 implementation does not silently claim perfect memory. If the requested information is not found in supplied history, the AI prompt requires it to say so.
