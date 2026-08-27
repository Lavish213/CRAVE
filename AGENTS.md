# CRAVE agent entrypoint

Before changing CRAVE, read `docs/AI_AGENT_HANDOFF.md` and `CRAVE_STATUS.md`. For product or ranking work, also read the relevant file under `docs/doctrine/`.

The repository is the source of truth. Chat transcripts, old audit scores, screenshots, and dated sections of `CRAVE_REMAINING_WORK.md` may be stale. Verify every claimed bug against the current branch before changing code.

Do not weaken the product invariants in `CRAVE_STATUS.md`. In particular, city-percentile tiers describe place standing, not personal taste; clicks are not confirmed outcomes; retries reuse an idempotency key; and LLM output is never catalog truth.

For implementation work:

1. Reproduce or verify the gap in current code.
2. Add or update a focused test that fails for the right reason.
3. Make the smallest complete end-to-end fix. Do not create parallel components or services when an established path exists.
4. Run the focused test, then the full affected suite and type checker.
5. Record device-only verification honestly instead of claiming it from unit tests.
6. Keep unrelated user changes and secrets untouched. Never commit `.env` files or credentials.

Do not merge, deploy, rotate credentials, alter paid-service settings, or make App Store submissions without explicit authorization.
