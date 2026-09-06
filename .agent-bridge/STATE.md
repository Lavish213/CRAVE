# Active agent state

Status: merged — code hardening complete; external release-certification gates remain
Owner: none
Branch: main
Phase 7 PR: #138 — merged
Phase 7 merge SHA: ee77d30279577cddfdcaaf1c54153bf0597a212f
Superseded PR: #137 — closed unmerged; replaced by #138 on the same Phase-7 branch lineage
Scope: `CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_EXECUTION_SPEC.md`

## Phase status

- Phases 1–5: merged.
- Phase 5 follow-up PR #136: merged as `8900039a8c7c14b3db22696af6942fa7113d2dd3`.
- Phase 6 PR #135: merged as `e7e19d73e4505282abab0009f9e98edbda3d63c5`.
- Phase 7 PR #138: merged as `ee77d30279577cddfdcaaf1c54153bf0597a212f`.

## Phase 7 shipped fixes

- Account deletion now removes user-associated profile/social/activity/recommendation/saves/craves/streak/push/report/media data and user-uploaded R2 objects, with retryable fail-closed storage/auth semantics.
- Incomplete deletion is surfaced as an API failure; the frontend does not sign out and falsely report success.
- Settings deletion copy matches the actual destructive scope.
- Settings displays the native application/build version instead of a manually hardcoded version string.
- The in-app privacy policy matches implemented deletion/retention behavior and no longer claims an unverified frontend Sentry crash integration.
- OTA runtime policy was deliberately not invented: the repo does not prove active `expo-updates`/`updates.url`/`runtimeVersion` use.

## Final automated verification

Exact Phase-7 final PR head `663cc323b368a7b44d0a214df20b862985934110` passed:

- CI workflow #512: **success**.
- CodeQL workflow #477: **success**.
- Frontend TypeScript: clean.
- Frontend Jest: **400/400 passed, 39 suites**.
- Backend SQLite: **1035 passed, 6 skipped** on the verified implementation gate.
- Real-Postgres migration/test lane: success.
- Alembic: exactly one head.
- `pip-audit`: no known vulnerabilities on the verified implementation gate.
- Conflict-marker guard: success.

CodeRabbit did not return an actionable Phase-7 finding before merge; its manual review attempt was explicitly quota/rate limited. That capacity result was not treated as an approval.

## External release-certification gates still open

CRAVE must **not** be called fully release-certified until these are completed outside repo-only CI:

- Real iOS + Android camera/microphone/permission regression, including blocked-permission Settings recovery and background/foreground transitions.
- VoiceOver + TalkBack pass across primary flows; Dynamic Type, focus order, touch targets, contrast, and reduced-motion checks.
- Hosted privacy-policy URL in store metadata.
- Google Play external web account-deletion resource in addition to the in-app path.
- App Store privacy declarations and Google Play Data Safety declarations matched to final runtime behavior and SDKs.
- Final signing, production secrets/API URLs, Android Maps key restrictions, push/upload configuration, and store-console validation.
- Production-build client/native crash and unhandled-JS observability verification.

## Next action

No engineering phase is currently claimed. The next work is **release certification**, not another hardening phase. Do not reopen Phases 1–7 without a proven regression or an explicitly approved new scope.
