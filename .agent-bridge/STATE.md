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

## Release-certification housekeeping (Claude, 2026-09-06)

Two small docs-only items, not a reopened phase:

- `docs/SENTRY_PRODUCTION_VERIFICATION.md` (PR #140) — permanent
  runbook for confirming `SENTRY_DSN`/`APP_ENV`/`DEBUG_API_KEY` are set
  in the production Railway environment and that a real event reaches
  Sentry. Repo-side wiring was already verified; the runbook itself
  still needs someone with Railway + Sentry dashboard access to
  actually run it — **Sentry production certification remains
  UNVERIFIED** until that happens and a successful event is recorded.
- `docs/PRODUCTION_CREDENTIAL_LEAKAGE_AUDIT_2026-09-06.md` (PR #141) —
  repo-scope audit for committed secrets / hardcoded credentials /
  dev-value leakage into a production build. **Result: PASS.** See
  that PR/doc for the full evidence; one dependency noted (not a
  leak): `secret_key`'s placeholder-default safety is conditional on
  Railway's `APP_ENV=prod` actually being set.

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

No engineering phase is currently claimed. The next work is **release certification**, not another hardening phase. Do not reopen Phases 1–7 without a proven regression or an explicitly approved new scope.

Open release-certification items (per the user-approved roadmap):
hosted legal pages (Privacy Policy + Google Play account-deletion page,
Codex workstream), Sentry production verification (UNVERIFIED, see
above — needs Railway/Sentry dashboard access), production
infrastructure verification (API URL, Supabase, R2, push config, Maps
key restrictions, and confirming `APP_ENV=prod` specifically — the
`secret_key` dependency above), EAS/native production build, physical-
device certification, accessibility certification, and store
compliance. Production credential leakage is the one item now fully
closed: **PASS**, see above.

Running in parallel, not blocking release certification: the product-
design workstream above (screen inventory + UX/design audit filed;
the actual screen-by-screen polish pass is the next step once that
doc is reviewed).
