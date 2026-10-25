# LEMMIQ V2.12 QA checklist

## Release gate (must pass before beta)
- [ ] Repository backed up; updater dry-run succeeds on actual Windows project
- [ ] `git diff` contains only intended additions; no Q/USDT wallet or earning-rules changes
- [ ] Full Android Gradle build passes; install using original signing key
- [ ] Render DB migration is additive, no table deletion
- [ ] GET `/app-config` reports 2.12.0, authentication and normal chats work
- [ ] Image config reports `enabled=false` until admin intentionally enables
- [ ] API key only on server; no credentials committed or logged
- [ ] Storage configured with private authenticated access

## PWA
- [ ] Q assistant Create Image opens dialog
- [ ] Direct chat composer 🎨 button opens dialog
- [ ] Group chat composer 🎨 button opens dialog
- [ ] Prompt validation, sizes and quote shown
- [ ] During generation, spinner/status shown, no duplicate generation click
- [ ] Successful image privately previews and is NOT sent automatically
- [ ] Send selected chat/group creates one photo attachment with proper sender
- [ ] Q assistant chooses recipient before sending
- [ ] Save generated image works
- [ ] Regenerate bills each new successful generation as configured
- [ ] Receiver sees new image and gets appropriate message notification
- [ ] Recipient cannot access original private draft URL

## Android
- [ ] Q Create Image entry renders in Q assistant
- [ ] Q Image entry in direct chat attachment menu
- [ ] Image preview displays correctly
- [ ] Select chat/group in Q assistant, explicit Send only
- [ ] Direct chat Send refreshes conversation
- [ ] Back/dismiss does not silently send
- [ ] Previously fixed Back/call/camera/profile flows remain stable

## Q and provider
- [ ] `Q_IMAGE` appears under Master Admin global feature pricing
- [ ] With charging disabled, image usage shows 0 Q
- [ ] When global pricing enabled and Q_IMAGE priced, successful generation debits exactly once
- [ ] Insufficient Q is rejected before image generation
- [ ] Provider HTTP errors, moderation rejection, or storage failure refund reserved Q
- [ ] Retrying same `request_id` does not double charge
- [ ] Same draft can only be sent once
- [ ] Daily limit 3 is enforced; separate users have separate limits
- [ ] Stale pending job gets reconciled and refunded after 15+ minutes upon user's next request
- [ ] Moderator flags inappropriate prompts/outputs
- [ ] Original Q Wallet, Q Ledger, withdrawals, packages, Q Predict unchanged
- [ ] Q Exchange not present/enabled

## Operational risk
- [ ] Run 2-account device test and moderate malicious prompt test
- [ ] Monitor provider cost per successful and failed request
- [ ] Review logs for user IDs without leaking full prompts or credentials
- [ ] Confirm pending-job handling under Render restart, and finish privacy/media deletion policy before public release
