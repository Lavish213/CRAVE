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

## Release-certification housekeeping (Claude, 2026-09-06)

Two small docs-only items, not a reopened phase:

- `docs/SENTRY_PRODUCTION_VERIFICATION.md` (PR #140) — permanent
  runbook for confirming `SENTRY_DSN`/`APP_ENV`/`DEBUG_API_KEY` are set
  in the production Railway environment and that a real event reaches
  Sentry. Repo-side wiring was already verified; the runbook itself
  still needs someone with Railway + Sentry dashboard access to
  actually run it — **Sentry production certification remains
  UNVERIFIED** until that happens and a successful event is recorded.
- `docs/PRODUCTION_CREDENTIAL_LEAKAGE_AUDIT_2026-09-06.md` — repo-scope
  audit for committed secrets / hardcoded credentials / dev-value
  leakage into a production build. **Result: PASS.** No committed
  `.env`/secret files (confirmed across full git history, not just the
  current tree), no hardcoded API keys/tokens/DSNs/service-role
  keys/DB URLs, `EXPO_PUBLIC_*` usage is limited to 4 vars that are all
  legitimately public-safe by design, CI/EAS/GitHub Actions configs use
  proper env-var/secrets-context indirection throughout. One dependency
  noted, not a leak: `secret_key`'s insecure placeholder default is
  caught by a hard-fail-on-boot check in `app/main.py`, but that check
  only runs when `APP_ENV=prod` — so its safety is conditional on the
  still-open production-infrastructure-verification step below, not
  something this audit can close on its own.

## Product-design workstream (Claude, 2026-09-06) — separate from release certification

User-approved, running in parallel with Codex's release-certification
work (legal pages, infra) rather than blocking on it. Not an
engineering phase, not a reopening of Phases 1-7: a screen-by-screen
UX/design audit to establish what the "product polish" pass should
actually target, since the app's logic is release-mature but its
visual identity is explicitly not yet locked (per the user's own
framing: consistent typography/cards/motion/spacing across Feed, Map,
Craves, Rankings, Place Detail, Profile, Settings, media capture, and
permission flows, plus the "no generic AI-app layout" uniqueness rule).

- `docs/SCREEN_INVENTORY_UX_DESIGN_AUDIT_2026-09-06.md` (PR to be
  opened) — full inventory of all 20 routes plus 13 shared components,
  audited against a 5-category framework (navigation/hierarchy,
  discovery cohesion, place-experience hub, state design, visual
  identity). Key findings: no shared `Typography` scale exists
  anywhere (screens hand-type 7-14+ distinct fontSize values each);
  `Shadows` token exists but only 3 of ~13 components use it (most
  cards render as flat, unelevated boxes); `PlaceCard`/
  `PlaceCardCompact` duplicate the same derivation logic in two
  separately-hand-typed style sheets; two parallel ranked-row
  implementations exist (`RankedPlaceRow` vs. Leaderboard's/Craves'
  hand-rolled rows) where one should do; a handful of concrete,
  screen-specific state-design gaps (Rank's non-functional retry
  button, record-video's silent recordAsync failure, Leaderboard's
  missing Friends-sign-in state, account deletion's under-weighted
  visual treatment vs. Sign Out). Full detail and per-screen findings
  in the doc itself.
- This audit is research only, no code changed. It recommends
  splitting future work into systemic fixes (a real Typography scale,
  a Shadows-adoption decision, consolidating the duplicated
  card/row components) versus the screen-specific polish pass itself,
  in the evidence-supported priority order: Feed → Place Detail → Map
  → Craves/Rankings → Profile/Settings → edge-state screens.

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

**2026-09-06, later**: the screen/UX track (Section 10 of the matrix)
was upgraded from "polish pass" to a real redesign — see
`docs/DESIGN_EXPLORATION_LOG.md` for Round 1 of visual-direction
mockups (rejected star ratings and Tinder-style swipe interaction,
promoted Decision Session as the Feed's primary surface per the
existing execution brief, kept photography emphasis, left light/dark
theme explicitly undecided). Sections 6/7's device/accessibility
runbooks and the screenshot-capture plan are scoped to the *current*
screens and are historical-baseline evidence only once the redesign
lands — they will need a fresh pass against the redesigned screens,
not a retrofit.
