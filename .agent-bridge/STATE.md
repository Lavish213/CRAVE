# Active agent state

Status: code hardening complete; release certification tracked entirely in the Master Matrix
Owner: none
Branch: main
Scope: `CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_EXECUTION_SPEC.md` (phases) + `docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md` (everything since)

## Phase status (all merged, none reopened)

- Phases 1-5: merged.
- Phase 5 follow-up PR #136: merged as `8900039a8c7c14b3db22696af6942fa7113d2dd3`.
- Phase 6 PR #135: merged as `e7e19d73e4505282abab0009f9e98edbda3d63c5`.
- Phase 7 PR #138: merged as `ee77d30279577cddfdcaaf1c54153bf0597a212f` (account deletion now removes user-associated profile/social/activity/recommendation/saves/craves/streak/push/report/media data and R2 objects, fail-closed; in-app privacy policy matches actual behavior; native app/build version shown instead of a hardcoded string; OTA/`expo-updates` policy deliberately not invented).
- Final Phase 7 verification: CI + CodeQL green, Frontend 400/400 (39 suites), Backend SQLite 1035 passed/6 skipped, real-Postgres lane green, Alembic one head, `pip-audit` clean.

Do not reopen Phases 1-7 without a proven regression or an explicitly approved new scope. A certification failure below becomes a narrow bugfix PR (Master Matrix Section 12), never a new hardening phase.

## Controlling document: Master Release Certification Matrix

`docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md` is **the** controlling document for everything remaining before CRAVE ships. Every requirement is tracked there with a status (PASS / READY FOR HUMAN VERIFICATION / BLOCKED ON ACCESS / NOT STARTED / FAILED), a bucket (1: repo-only / 2: prepared-for-human / 3: requires credentials-devices-consoles / 4: reopen-code-on-failure policy), and — where work exists — exact evidence, procedure, expected result, responsible environment, and remediation path. Do not duplicate its tracking here; update the matrix directly as items close and keep this section a pointer + one-line status.

**2026-09-06 — all four certification/audit PRs from today merged, in this order:**

| PR | Content | Merge SHA |
|---|---|---|
| #141 | Production credential leakage audit — **PASS** | `2328e126a62a5cf4e0f4b921bd5d414b7f394934` |
| #140 | Sentry production verification runbook | `aa156a5dffadc167ddd7052013cf589c553707b3` |
| #143 | Screen inventory + UX/design audit | `416ada11179605a2a64d13ed8e7d2485b7ce4473` |
| #144 | Master release certification matrix (+ absorbed PR #142, Codex's independently-opened companion matrix, closed in favor of this one) | `633a5ebedc43de0dde5a42394608c17928049d89` |

CodeRabbit was capacity-limited on every one of these for 2+ hours despite repeated triggers; all four merged on CI-green + docs-only-risk grounds, following the same precedent this repo already set for Phase 6/7 (capacity-limited is not treated as a false approval, but isn't required to block a zero-application-code change either).

**Current matrix read (Section 11):** 5 items **PASS**, 1 **PASS, conditional** (the `SECRET_KEY` hard-fail gate, conditional on `APP_ENV=prod`), **11 READY FOR HUMAN VERIFICATION** (Sentry, Railway env vars, Supabase, R2, push, Google Maps/Places, EAS signing, EAS build, physical-device certification, accessibility certification, final smoke test, Privacy Nutrition Labels/Data Safety mapping, store metadata/screenshots). Genuinely **NOT STARTED**: hosted legal pages (blocked on a hosting decision), the final pre-submission policy refresh (by design never permanently PASS), the client/native crash-observability decision, Performance & Resilience certification (no runbook yet), Play Console URL field entry, UGC/moderation representation.

Supporting docs added this pass: `docs/RAILWAY_PRODUCTION_ENV_VERIFICATION.md`, `docs/RUNBOOK_SUPABASE_PRODUCTION.md`, `docs/RUNBOOK_R2_PRODUCTION.md`, `docs/RUNBOOK_GOOGLE_MAPS_PLACES_PRODUCTION.md`, `docs/RUNBOOK_PUSH_NOTIFICATIONS_PRODUCTION.md`, `docs/RUNBOOK_EAS_SIGNING_PRODUCTION_BUILD.md`, `docs/RUNBOOK_PHYSICAL_DEVICE_CERTIFICATION.md`, `docs/RUNBOOK_ACCESSIBILITY_CERTIFICATION.md`, `docs/RUNBOOK_FINAL_RELEASE_SMOKE_TEST.md`, `docs/PRODUCTION_ENVIRONMENT_MANIFEST.md`, `docs/PROVIDER_DATA_FLOW_INVENTORY.md`, `docs/SCREEN_UX_FINDINGS_TRIAGE.md`, `docs/RELEASE_TEST_ACCOUNTS_AND_FIXTURES.md`, `docs/RELEASE_ROLLBACK_PROCEDURES.md`, `docs/STORE_METADATA_DRAFT.md`, `docs/SCREENSHOT_CAPTURE_PLAN.md`.

## Product-design workstream — now a redesign, not a polish pass

`docs/SCREEN_INVENTORY_UX_DESIGN_AUDIT_2026-09-06.md` (PR #143) found: no shared `Typography` scale anywhere; `Shadows` token defined but only ~3 of 13 components use it; `PlaceCard`/`PlaceCardCompact` duplicate derivation logic; two parallel ranked-row implementations; 4 real RELEASE DEFECT bugs (Rank's non-functional retry button, `record-video`'s silent recording failure, Leaderboard's missing Friends-sign-in state, account deletion's under-weighted visual treatment vs. Sign Out) — sorted along with everything else into `docs/SCREEN_UX_FINDINGS_TRIAGE.md` (RELEASE DEFECT / ACCESSIBILITY / PRE-RELEASE POLISH / POST-LAUNCH).

User explicitly upgraded scope from "polish pass" to a real redesign ("the shipped app is ass so were doing a redesign"). `docs/DESIGN_EXPLORATION_LOG.md` tracks mockup rounds so reactions persist: **Round 1 done** — rejected D's star-rating model (conflicts with CRAVE's actual ranking mechanic) and A's Tinder-style swipe interaction; promoted B's Decision-Session-as-primary-Feed-surface hierarchy (matches the pre-existing execution brief's own stated intent); kept A's photography emphasis; deprioritized C's editorial-magazine architecture as core Feed structure; explicitly left light/dark theme undecided from the mockups. Thesis: **"CRAVE = appetite first, visually. Decision intelligence, underneath it."** Round 2 briefed (four structural variants of that thesis under Photography × Decision Intelligence × Dark CRAVE × No Stars × No Swipe-Dating UI) but not yet generated.

Master Matrix Section 6/7's device/accessibility runbooks and the screenshot-capture plan are scoped to the *current* (pre-redesign) screens — historical-baseline evidence only, will need a fresh pass once the redesign lands, not a retrofit.

## Next action

No engineering phase is currently claimed. Release certification is tracked entirely in the Master Matrix, whose own Section 11 read says: any future certification run should be almost entirely **execution**, not **research** — read the matrix, run the Section 5.0 preflight gate, execute each prepared runbook in order, attach evidence, mark PASS/FAIL, open a narrow bugfix PR only if something fails.

Everything genuinely open now requires either external access this session doesn't have (Railway/Sentry/Supabase/Cloudflare/Google/Apple/Play Console dashboards, physical iOS/Android devices) or further design/implementation work (the redesign itself, the 4 RELEASE DEFECT bugfixes, the Performance & Resilience runbook, the client/native crash-observability decision, the hosted legal pages). "Finish all certifications" is complete in the sense that every repo-only certification/audit artifact that can exist now exists and is merged to `main` — not in the sense that CRAVE is store-submitted.
