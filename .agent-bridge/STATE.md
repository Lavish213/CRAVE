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

## Controlling document: Master Release Certification Matrix

`docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md` (PR to be opened) is now
**the** controlling document for everything remaining before CRAVE
ships — supersedes the bullet list that used to live in this section.
Every requirement is tracked there with a status (PASS / READY FOR
HUMAN VERIFICATION / BLOCKED ON ACCESS / NOT STARTED / FAILED), bucket
(1: Codex autonomous, 2: Codex prepares/human executes, 3: requires
credentials/devices/consoles, 4: reopen-code-on-failure policy), and
— where work exists — exact evidence, procedure, expected result,
responsible environment, and remediation path.

Current read (Section 11 of that doc): 5 items **PASS** (credential
leakage, the prod-config hard-fail gate's code side, bundle/package
IDs, EAS build profiles, permission-explanation strings), 2 **READY
FOR HUMAN VERIFICATION** (Sentry — PR #140; Railway env vars —
`docs/RAILWAY_PRODUCTION_ENV_VERIFICATION.md`, formalizing
`_validate_prod_config()`'s own checklist the same way the Sentry doc
did), everything else either **BLOCKED ON ACCESS** (Apple/Android
signing credentials — genuinely can't be checked from a repo session)
or **NOT STARTED** (hosted legal pages, Supabase/R2/push/Maps
production config runbooks, EAS signing, physical-device/
accessibility/smoke-test scripts, store metadata drafts). Do not
duplicate that tracking here — update the matrix directly as items
close, and keep this section as a pointer + one-line status, not a
second copy of the list.

Also tracked there (Section 10): the product-design workstream
(`docs/SCREEN_INVENTORY_UX_DESIGN_AUDIT_2026-09-06.md`, PR #143) —
audit complete, screen-by-screen polish not yet started, running in
parallel with (not blocking) the certification sections above.

## Next action

No engineering phase is currently claimed. The next work is **release
certification**, tracked entirely in the Master Matrix above. Do not
reopen Phases 1-7 without a proven regression or an explicitly
approved new scope — a certification failure becomes a narrow bugfix
PR (Section 12 of the matrix), never a new hardening phase.

Highest-leverage next bucket-1 work per the matrix: Section 4's
remaining procedure gaps (Supabase, R2, push, Maps — Sentry and
Railway env vars both now have runbooks) and drafting the App Store/
Play Store metadata items (Section 8.2, 8.4) that don't need console
access to draft.
