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

**2026-09-06 update**: Codex independently opened its own competing
matrix (PR #142, `docs/CRAVE_MASTER_RELEASE_CERTIFICATION_MATRIX.md`)
~7 minutes before this one, against the same base, neither of us
having seen the other first. Per explicit user direction, PR #144 is
authoritative; #142's unique value (a Performance & Resilience
category, granular device/accessibility framing, an explicit client-
Sentry-absence callout, a flat submission checklist) was folded into
#144 before closing #142. There is now exactly one controlling
document.

Current read (Section 11 of that doc, post-consolidation): 5 items
**PASS**, 1 **PASS, conditional**, **11 READY FOR HUMAN VERIFICATION**
— every Section 4 config runbook (Sentry, Railway env vars, Supabase,
R2, push, Google Maps/Places), EAS signing/build, physical-device
certification, accessibility certification, the final smoke test, and
the Section 8 store-drafting items now have a complete, repo-verified
procedure. What's genuinely still open: hosted legal pages (blocked on
a hosting decision), the final pre-submission policy refresh (by
design never permanently PASS), the client/native crash-observability
decision, Performance & Resilience certification (no runbook yet),
Play Console URL field entry, and UGC/moderation representation.
New supporting docs this pass: `docs/PRODUCTION_ENVIRONMENT_MANIFEST.md`,
`docs/PROVIDER_DATA_FLOW_INVENTORY.md`,
`docs/SCREEN_UX_FINDINGS_TRIAGE.md` (every PR #143 finding sorted into
RELEASE DEFECT/ACCESSIBILITY/PRE-RELEASE POLISH/POST-LAUNCH — 4 real
defects found), `docs/RELEASE_TEST_ACCOUNTS_AND_FIXTURES.md`,
`docs/RELEASE_ROLLBACK_PROCEDURES.md`, `docs/STORE_METADATA_DRAFT.md`,
`docs/SCREENSHOT_CAPTURE_PLAN.md`, and 4 new runbooks (EAS signing,
physical-device, accessibility, final-smoke-test) plus the 4 remaining
Section 4 config runbooks (Supabase, R2, Maps, push). Do not duplicate
that tracking here — update the matrix directly as items close, and
keep this section as a pointer + one-line status, not a second copy
of the list.

## Next action

No engineering phase is currently claimed. The next work is **release
certification**, tracked entirely in the Master Matrix above, whose
own read of itself now says: Codex's certification run should be
almost entirely **execution**, not **research** — read the matrix, run
the Section 5.0 preflight gate, execute each prepared runbook in
order, attach evidence, mark PASS/FAIL, open a narrow bugfix PR only
if something fails. Do not reopen Phases 1-7 without a proven
regression or an explicitly approved new scope — a certification
failure becomes a narrow bugfix PR (Section 12 of the matrix), never a
new hardening phase.

Remaining bucket-1 gaps (per the matrix's own Section 11 read): the
Performance & Resilience runbook (Section 6a) has no procedure yet;
the client/native crash-observability decision (4.6) needs an actual
decision, not just documentation that it's undecided; and the 4
RELEASE DEFECT items in `docs/SCREEN_UX_FINDINGS_TRIAGE.md` (Rank's
non-functional retry, record-video's silent recording failure,
Leaderboard's missing Friends-sign-in state, account deletion's
under-weighted visual treatment) should become narrow bugfix PRs
before or alongside certification, not after.
