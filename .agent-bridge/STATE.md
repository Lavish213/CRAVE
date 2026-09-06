# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/phase7-release-hardening
Base SHA: 8900039a8c7c14b3db22696af6942fa7113d2dd3 (main, post-Phase-5 follow-up PR #136)
PR: #138 — Phase 7: Release hardening and account-deletion integrity
Superseded PR: #137 — closed unmerged only because GitHub's GraphQL rate limit blocked the draft→ready transition; #138 uses the same branch/head lineage.
Implementation head before handoff-only commits: 1057fd0d5557dc91890457e76c97ee170f3f67d6
Scope: Phase 7 of `CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_EXECUTION_SPEC.md` — release hardening only.

## Merged baseline

- Phases 1–5: merged.
- Phase 5 follow-up PR #136: merged as `8900039a8c7c14b3db22696af6942fa7113d2dd3`; all actionable CodeRabbit findings resolved before merge.
- Phase 6 PR #135: merged as `e7e19d73e4505282abab0009f9e98edbda3d63c5` and included in the Phase-7 base.

## Confirmed Phase-7 fixes

### Account deletion integrity

`backend/app/services/account/account_deletion_service.py` now deletes data that remains associated with the requesting user across CRAVE's profile/social/activity/recommendation/saves/craves/streak/push/report/media graph, deletes user-uploaded R2 objects, then deletes the Supabase Auth identity.

Order and failure semantics are deliberate and retryable:

1. User-owned image/video R2 objects (`orig_key`, `processed_key`, `thumb_key`) are deleted first. Storage failure fails closed before DB/auth deletion; object deletion is idempotent for retry.
2. App-side rows are deleted in one DB transaction. DB failure rolls back DB changes and returns incomplete.
3. Supabase Auth is deleted last. Upstream/auth failure returns incomplete instead of pretending the account is gone. App-side deletion is idempotent, so a later retry can finish the auth half.

The deletion sweep includes user profile, follows/blocks both directions, personal rankings, activity events (actor/target), recommendation events, hitlist saves/suggestions/dedup keys, Crave shares, menu submissions, push tokens, streak state, authored media reports, reports against owned media, and user-owned image/video rows. `reviewed_by` references on retained moderation records are anonymized where applicable.

Public catalog facts that no longer contain a user identifier are not deleted solely because they originated from a user contribution. Example: an approved menu submission may have materialized anonymous `PlaceClaim` facts; those no longer identify the deleted account.

`backend/app/api/v1/routes/account.py` now returns HTTP 502 when deletion is incomplete, so the client cannot sign out and tell the user deletion succeeded while storage/auth cleanup is unfinished.

`frontend/app/settings.tsx` keeps the session active and shows a retryable error when account deletion fails; success still signs out only after the backend reports completion. Destructive copy now matches the actual deletion contract.

### Release/config truth

`frontend/app/settings.tsx` no longer hardcodes `1.0.0`. It displays `expo-application` native application version and native build version, so EAS/native build numbering is what users see.

OTA runtime policy remains **REJECTED / NOT CONFIGURED**: current repo config does not prove actual `expo-updates`/`updates.url`/`runtimeVersion` use. Phase 7 did not invent an OTA architecture just because EAS channel names exist.

### Privacy truth

`frontend/app/legal/privacy.tsx` now matches the implemented deletion/retention behavior and no longer claims a separate in-app Sentry crash SDK that the frontend does not ship. It documents operational hosting logs, deletion failure truth, and the distinction between personal account data and anonymous public restaurant facts.

Backend dependencies include `sentry-sdk`, but this audit did not find repo evidence of `sentry_sdk.init` or `SENTRY_DSN`; therefore no backend Sentry-runtime claim is made from the dependency alone.

## Regression coverage / final code verification

Exact implementation head `1057fd0d5557dc91890457e76c97ee170f3f67d6` passed:

- GitHub CI workflow #509: **success**.
- CodeQL workflow #474: **success**.
- Frontend TypeScript: clean.
- Frontend Jest: **400/400 passed, 39 suites**.
- Backend SQLite: **1035 passed, 6 skipped**.
- Backend real-Postgres lane: full migration chain from empty, newest migration downgrade/re-upgrade, and test suite: **success**.
- Alembic: exactly one head.
- Dependency scan (`pip-audit`): **No known vulnerabilities found**.
- Conflict-marker guard: **success**.

Handoff head `a65177c18943401b404c6e535bdc26e744fda331` also passed the full gate in superseded draft PR #137:

- GitHub CI workflow #510: **success**.
- CodeQL workflow #475: **success**.
- Frontend typecheck/tests: **success**.
- Backend SQLite/Postgres/migrations/dependency scan/guard: **success**.

The first Phase-7 CI head found only two stale Settings test expectations (old hardcoded version and old deletion-error copy). They were updated to assert the new production contract; no production rollback was made.

## Explicit release-certification gates still open

These cannot be truthfully satisfied by repo-only CI and must remain release blockers until separately verified:

- Real iOS + Android camera/microphone/permission regression, including blocked-permission Settings recovery and background/foreground transitions.
- VoiceOver + TalkBack pass across primary flows; Dynamic Type, focus order, touch targets, contrast, reduced-motion behavior where applicable.
- Hosted privacy-policy URL in store metadata.
- Google Play external web account-deletion resource in addition to the in-app path.
- App Store privacy declarations / Google Play Data Safety declarations matched to final runtime behavior and third-party SDKs.
- Final signing, production secrets/API URLs, Android Maps key restrictions, push/upload configuration, and store-console validation.
- Client/native crash and unhandled-JS observability must be verified on production builds; no claim is made from CI alone.

Phase 7 code hardening can merge with these residuals documented, but CRAVE must **not** be called fully release-certified until the native/store gates above are completed.

## Review / merge gate

- PR #138 is open and non-draft on the same Phase-7 branch.
- CodeRabbit manual review on #137 was explicitly rate-limited, with no actionable finding returned. That capacity result is not treated as an approval or a bug report.
- Require CI + CodeQL green on the exact #138 final head after this PR-number-only handoff commit.
- Read actual #138 review content; fix only verified actionable findings.
- Merge with expected head SHA only when the final exact-head checks are green and no actionable review finding is outstanding.

## Next action

Run the final PR-#138 head CI/CodeQL gate, inspect CodeRabbit/review content as available, resolve any real finding, then squash-merge Phase 7. Do not start new feature work in this branch.
