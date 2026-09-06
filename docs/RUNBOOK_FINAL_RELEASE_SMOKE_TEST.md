# Final release smoke test runbook

Permanent runbook. The last gate before submission — run once, on the
**exact** signed candidate intended for the store, pointed at real
production infrastructure, after every other certification section
has already passed. This is not a re-run of the physical-device
matrix; it's one linear, realistic user journey end to end.

## Prerequisites

- Every Section 4 (production infrastructure) runbook has passed.
- The signed release candidate from
  `docs/RUNBOOK_EAS_SIGNING_PRODUCTION_BUILD.md`.
- A disposable test account (see
  `docs/RELEASE_TEST_ACCOUNTS_AND_FIXTURES.md`'s "fresh account" and
  "disposable deletion account" definitions — this smoke test uses
  the latter, since it ends in account deletion).
- `GET /api/v1/debug/version` and `GET /api/v1/debug/recommendation-events`
  available for verification steps.

## The journey (one continuous session, don't skip steps)

1. **Confirm build identity.** Note the exact iOS/Android version+build
   shown in Settings, and `GET /api/v1/debug/version`'s commit —
   record both in the release-candidate identity record (matrix
   Section 5.5) before doing anything else.
2. **Fresh account creation.** Sign up with a real (disposable) Google
   or Apple account, complete `profile-setup.tsx`'s username claim.
3. **Discovery.** Open Feed, confirm real production data loads
   (tiered sections render, not an empty/error state). Open Map,
   confirm markers render. Use Search, confirm results return.
4. **Place Detail.** Open a real place, confirm menu/photos/videos
   render where they exist.
5. **Rank.** Rank at least one place through the full tier → compare
   → done flow; confirm the score-reveal renders and the ranking
   persists (visible on Profile afterward).
6. **Save + Craves.** Save a place; confirm it appears in Craves.
7. **Media upload.** Record and upload one short video, and upload one
   photo, through the real flows (`record-video`, Place Detail's photo
   action). Confirm both appear where expected (Place Detail's video
   gallery / photo gallery) after processing completes.
8. **Telemetry sanity.** Query
   `GET /api/v1/debug/recommendation-events?user_id=<this account>`
   (or by whatever filter is available) and confirm impression/save/
   rank events from this session actually landed, with the expected
   `event_type`/`place_id`/context — not just that the UI didn't
   error.
9. **Push.** Trigger whatever real event sends a push to this account
   (per `docs/RUNBOOK_PUSH_NOTIFICATIONS_PRODUCTION.md`) and confirm
   it arrives on the device.
10. **Sentry sanity** (if `SENTRY_DSN` is set for production). Run
    `docs/SENTRY_PRODUCTION_VERIFICATION.md`'s Proof 2/3 once more
    against this exact deployment, since a smoke test is a reasonable
    moment to re-confirm observability is live for the actual
    candidate being certified, not just "was live at some point."
11. **Logout / re-login.** Sign out, confirm signed-out state, sign
    back in, confirm all prior data (rankings, saves, craves, media)
    is still present and correctly attributed.
12. **Account deletion.** Delete the account through Settings' real
    flow. Confirm: the two-step confirmation fires, the app signs out
    on success, and — critically — verify server-side that the
    account and its data are actually gone (per Phase 7's scope:
    rankings/Craves/saves/photos/videos/reports removed, R2 objects
    deleted) rather than just trusting the client's "success" state.
13. **Post-deletion access check.** Attempt to sign back in with the
    same credentials; confirm the deleted identity cannot continue as
    an active account (the Supabase auth identity itself was removed,
    per `account_deletion_service.py`).

## Pass/fail

**Pass:** all 13 steps complete against real production infrastructure
with no manual workarounds, no data loss, and step 12's server-side
verification confirms actual deletion (not just a client-side
"success" toast).

**Fail:** any step failing here is bucket 4 — a narrow, scoped bugfix
PR against that specific step, per matrix Section 12. Since this test
already assumes every earlier certification section passed, a failure
here specifically at the *integration* level (individually-passing
pieces that don't work together) is worth flagging as such in the
bugfix PR's description, not just "step 7 failed."

## After running this

Record the full journey's result with the evidence conventions
(matrix's evidence-conventions section) — this is the one runbook
where the release-candidate identity record should be fully complete
by the time it's done. Update matrix Section 9.
