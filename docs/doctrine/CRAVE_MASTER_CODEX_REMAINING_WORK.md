# CRAVE Master Codex Remaining Work

Status: **CANONICAL — CODEX REMAINING WORK CHECKLIST**

## 1. Purpose

This is the single consolidated list of implementation work still owed to
Codex, current as of Wave 4 merging to `main`. It exists so Codex (or any
future agent) has one place to check before starting a task, rather than
re-deriving scope from the Migration Plan, the Readiness Audit, and 15
screen contracts separately every time. It does not replace those documents
as authority for *how* to build each item — it is the checklist of *what
remains*, grouped by the Migration Plan's own wave numbering.

If this file and `CRAVE_IMPLEMENTATION_MIGRATION_PLAN.md` or
`CRAVE_CODEX_READINESS_AUDIT.md` disagree on a rule (not a completion
status), the Migration Plan/Readiness Audit/screen contracts remain
authoritative per `CRAVE_CODEX_IMPLEMENTATION_RULES_V2.md`'s authority
order — update this file rather than treating the disagreement as license
to guess.

## 2. Completed baseline — do not redo

- **Wave 0** — protected `#146` release-defect baseline.
- **Wave 1** — shared foundations (PR #170): typography roles, shared
  Decision Strip, centralized resumable auth gate, recommendation-context/
  privacy/evidence primitives.
- **Wave 2** — visit-evidence persistence + Rank ownership migration
  (PR #172): `declared|verified|inferred` tiers, Rank Home ownership,
  Profile handoff, deterministic Rank presentation mapping.
- **Wave 3** — navigation topology (PR #185): five tabs (Feed/Search/
  Craves/Rank/Profile), Map off the tab bar, persistent `+` → capture-only
  `food-evidence` screen, Activity as a header route.
- **Wave 4** — Feed / Decision Session hierarchy: merged to `main`.

Verified end-to-end against the current `main` head: backend
`compileall`/import/`pytest` clean (1043 passed, 2 skipped), single Alembic
head, frontend `tsc --noEmit` clean, `jest --ci` clean (426/426), conflict-
marker guard clean.

## 3. Remaining implementation work

### 3.1 Finish the remaining Feed dependencies from Wave 4
- Wire the real "From your Craves" rail once the Craves subset/source exists.
- Migrate useful social evidence out of `friends-feed.tsx` into the Feed.
- Preserve `friends-feed` temporarily for deep links until all callers migrate.
- Complete any durable context/reject/correction behavior that requires
  backend state rather than inventing local semantics.
- Add dish/taste-driven Feed modules only when real evidence exists.
- Never restore percentile buckets as Feed organization.
- Never resurrect `TrendingStrip` as a popularity rail.

These were explicitly identified as Feed implementation dependencies in
the Readiness Audit.

### 3.2 Wave 5 — Search backend + Search screen
- Build semantic natural-language constraint interpretation.
- Convert interpreted intent into the shared recommendation request/
  context contract.
- Support editable constraint chips.
- Implement exact restaurant-name bypass to Place Detail.
- Return a small bounded result set.
- Implement bounded "Show more."
- Implement zero-result relaxation for soft constraints only.
- Never relax allergies/dietary hard constraints silently.
- Support Craves-scoped Search.
- Support Rank-scoped Search.
- Preserve the approved Search language: "Best match for you" / "Safer
  pick" / "Worth exploring."
- Add a proper uncertain-interpretation state instead of turning Search
  into generic chat.

### 3.3 Wave 5 — Search ↔ Contextual Map plumbing
- Pass the exact Search candidate set to Map.
- Map must not independently rerank that set.
- Implement explicit "Search this area."
- Do not automatically refetch just because the user pans.
- Implement location-denied "Choose an area" fallback.
- Maintain list/map parity.
- Keep Map contextual rather than restoring it as a tab.
- Preserve source attribution so Feed/Search/Craves/Decision Session map
  launches remain distinguishable.
- Direct Map mode still needs to use the shared recommendation context
  instead of independent ranking.

### 3.4 Wave 6 — Craves intelligence
- Upgrade saved places from a stitched bookmarks screen into active
  decision intelligence.
- Build the prioritized "makes sense now" subset.
- Keep the complete saved pool available underneath.
- Automatic Want to Try / Tried state based on visit evidence.
- Visit-driven graduation.
- Preserve saves as saves; never reinterpret them as "likes" or "love."
- Show closed/materially changed notices when trustworthy data exists.
- Support save decay in recommendation influence without deleting the
  factual save.
- Preserve save IDs, history, cache, and provenance.
- Connect Craves candidate subset back into Feed.
- Connect Craves candidate subset into contextual Map.

### 3.5 Wave 7 — Place Detail relationship hierarchy
- Implement the four relationship modes: never visited / considering
  tonight / visited-not-regular / regular.
- Make the top of the page genuinely change with relationship state.
- Stop persuading the user after a confirmed visit.
- Use the shared Decision Strip.
- Remember why an unvisited place was saved/recommended.
- Implement adaptive primary CTA.
- Add correction action.
- Preserve working integrations rather than a full-screen rewrite.

Place Detail remains explicitly YELLOW because several real data
capabilities (§3.6-§3.10 below) are still missing.

### 3.6 Build trustworthy operational-data ingestion
- Current open/closed status.
- Hours/freshness.
- Provenance.
- Staleness handling.
- Conflicting-source handling.
- Omit data when trust is insufficient.
- Never fabricate operating status.
- Stale hours must be treated more strictly than stale menu information.

### 3.7 Build Dish Intelligence foundation
- Stable dish ID.
- Parent restaurant relationship.
- Dish name/identity normalization.
- Menu provenance.
- Menu freshness.
- Dish availability/staleness handling.
- Dish evidence independent from restaurant-level evidence.
- Dish ↔ user taste signals.
- Dish save/react/share capability at the approved V1 level.
- Support restaurant recommendation because of a standout dish.
- No Dish Rank yet; that remains later.

### 3.8 Build the real taste graph
- Persist explicit taste evidence.
- Persist/infer confident taste traits: cuisine traits, flavor/dish
  tendencies, chain-vs-independent tendencies, price/value tendencies,
  travel willingness, novelty, negative preference evidence.
- Separate restaurant affinity from dish affinity.
- Explicit corrections outrank inference.
- Recent/session intent must not silently rewrite long-term taste.
- Deleted/retracted evidence must propagate through derived taste.
- Maintain factual-history vs. recommendation-influence separation.

### 3.9 Place Detail menu intelligence
- "Menu For You" only when evidence is sufficient.
- Full Menu fallback.
- Explain why dishes fit.
- Suppress personalized dish claims when menu evidence is stale/weak.
- Show menu provenance/freshness.
- Restaurant-submitted vs. organic evidence distinction.
- No fake personalized menu when Dish Intelligence is not ready.

### 3.10 Place Detail media provenance
- Hero selects strongest trustworthy evidence.
- User media vs. restaurant-submitted media clearly distinguished.
- No stock/fake restaurant imagery.
- Typography-led identity fallback when trustworthy imagery is absent.
- Avoid giant empty media space.

### 3.11 Wave 8 — Native Posting / Private Logging composer
- Build the actual unified composer.
- Keep private logging and public/social posting as separate outcomes.
- Flow: `capture → restaurant confirmation → dish confirmation → quick take → caption → visibility`.
- Media required for public/follow-scope post.
- Media not required for private food log.
- Visibility: private / approved-follow social scope / public.
- Visibility cannot be silently chosen.
- Support backdating.
- Support restaurant search/manual missing-place path.
- Implement dish confirmation when capability exists.
- Emit evidence only after successful commit.
- Edits recompute derived evidence.
- Delete retracts evidence.

### 3.12 Posting backend/write contracts
- Upload endpoint.
- Publish/commit endpoint.
- Private-log write endpoint.
- Restaurant association.
- Dish association.
- Visibility field.
- Idempotency/retry protection.
- Failure recovery.
- Media-upload state machine.
- Correct post-commit evidence emission.
- No half-created recommendation evidence on failed upload/publish.

### 3.13 Migrate `record-video`
- Reuse useful camera/permission logic.
- Reuse recording-failure UX protected by #146.
- Redirect old entry points only after composer parity.
- Preserve old deep links during transition.
- Retire only after no callers remain.

### 3.14 Migrate `add-spot`
- Reuse useful place-search/add-place logic.
- Move it underneath the new composer flow.
- Preserve compatible state/deep links while transitioning.
- Do not keep it as an independent final posting architecture.

### 3.15 Wave 9 — Profile completion
- Keep full Rank out of Profile.
- Add compact Rank status/link only.
- Implement real taste identity summary.
- Food history.
- User posts.
- Constrained/automatic food tagline rather than generic bio.
- Remove old `friends-feed` entry.
- No vanity follower/engagement counts.
- Maintain privacy defaults for Rank/Craves/history.

### 3.16 Wave 9 — Taste Profile
- Build the real inspectable taste model UI.
- Only display traits supported by real evidence.
- Use "Still learning" when confidence is insufficient.
- Correction actions: Not true / Doesn't matter / Less / More.
- Dietary/allergy/religious/ethical hard constraints.
- Novelty preference.
- Separate soft preferences from promoted hard constraints.
- Explain meaningful corrections.
- Never fabricate taste traits just to fill the screen.

### 3.17 Implement the three distinct personalization controls
- Pause personalization.
- Reset current recommendations/session.
- Reset inferred taste while preserving factual food history.
- These must remain distinct operations.
- Never implement one vague "Reset everything" action.

### 3.18 Wave 9 — Other User Profile
- Remove/default-block full personal Rank exposure.
- Only public identity/content allowed.
- Optional owner-approved coarse Rank highlights only.
- Taste compatibility only on deliberate profile navigation.
- Compute compatibility using approved taste data.
- Keep Mute separate from "don't use this person's taste to influence mine."
- Blocking must revoke prior visibility.
- No public-by-default sensitive taste information.

### 3.19 Build taste compatibility computation
- Compare only approved/shared coarse taste data.
- No hidden full Rank exposure.
- No scraping private user evidence.
- No follower/popularity influence.
- Compatibility is contextual information, not social ranking.

### 3.20 Wave 10 — Activity Inbox
- Build the actual screen.
- Build Activity API/event source.
- Event deep links.
- Follow requests.
- Rank reminders.
- Shared-Craves future-safe event type.
- Reservation/reopening events where capabilities exist.
- Low-priority batching.
- Inbox works even if push is denied.
- No generic engagement/re-engagement notifications.

### 3.21 Wave 10 — Cold-start calibration
- Anonymous user can reach a useful Feed before creating an account.
- Dietary/allergy constraints.
- One novelty starting-position question.
- 3-5 known restaurant reactions: Loved it / Good / Not for me.
- Optional coarse cuisine affinity.
- Everything except dietary disclosure is skippable.
- No direct price/travel interrogation.
- No onboarding Rank duels.
- End onboarding at usable Feed.

### 3.22 Anonymous recommendation bootstrap
- Defensible city-level baseline.
- Lower-confidence recommendation labeling.
- Do not claim personalized knowledge before enough evidence exists.
- Store anonymous evidence safely.
- Prepare anonymous→account migration.

### 3.23 Anonymous-to-account evidence migration
- Preserve legitimate pre-account interactions when account is created.
- No duplicate evidence.
- No silent semantic conversion.
- Preserve factual/recommendation-influence distinction.
- Ensure auth interruption resumes the original action.

### 3.24 Finish centralized auth-gate call-site migration
- Save. Rank. Post/log. Follow. Privacy-sensitive actions.
- Preserve pending action payload.
- Preserve return destination.
- Successful auth resumes action.
- Cancel returns safely.
- No screen-level duplicate AuthSheet semantics where centralized recovery
  should own it.

### 3.25 Wave 10 — Settings / Privacy Controls
- Separate: visibility / recommendation influence / factual retention /
  OS permissions / notification preferences.
- Account export.
- Account deletion.
- Recommendation controls.
- Taste reset controls.
- Post visibility defaults.
- Location permission controls.
- Notification controls.
- Destructive actions visually separated.

### 3.26 Privacy lifecycle backend
- Export user data.
- Delete user/account data.
- Delete/retract taste evidence.
- Propagate correction/deletion into derived intelligence.
- Clear privacy-sensitive caches on sign-out/deletion.
- Blocking revocation.
- Preserve factual history where user asked only to reset recommendation
  influence.
- Never conflate recommendation reset with data deletion.

### 3.27 `friends-feed.tsx` retirement
- Feed owns useful social evidence.
- Activity owns events/notifications.
- Remove navigation entry points.
- Deep-link redirect/handoff.
- Migrate tests.
- Delete route only when zero callers remain.

This retirement procedure is explicitly mandated.

### 3.28 `profile-setup.tsx` retirement/split
- Separate identity/username setup from food calibration.
- Remove old assumptions around public leaderboard/taste exposure.
- Move calibration to the canonical cold-start flow.
- Preserve valid account/profile fields during migration.

### 3.29 Leaderboard audit
- Do not expand it during implementation.
- Decide later whether it survives as breadth/activity only, or gets
  folded/deleted.
- Must never become social preference ranking.
- Preserve #146 signed-out Friends auth behavior while it exists.
- Never expose private Rank.

This remains **AUDIT REQUIRED**, not free Codex design territory.

### 3.30 Cache/storage migrations
- Preserve stable keys when semantics remain the same.
- Version keys when semantics change.
- One-time migration where otherwise user state would disappear.
- Never read an old cached value under a new meaning.
- Clear privacy-sensitive storage correctly.
- Verify Feed, Craves, Rank, Map, auth, Profile state migrations.

### 3.31 Analytics/recommendation-ledger migration
- Preserve existing event meaning.
- Correct `surface` values after route ownership changes.
- Parent-aware Map attribution.
- No double-counting during compatibility periods.
- Preserve Decision Session role/impression/click semantics.
- Retire old route analytics only after route retirement.

### 3.32 Deep-link migration table
Maintain, for every old route (Map, `friends-feed`, `record-video`,
`add-spot`, old Profile Rank entry points, auth-return routes):
- old path
- target path
- handoff behavior
- preserved parameters
- deletion condition

### 3.33 Offline/stale-state completion
- Saved Craves available offline where feasible.
- Recent Place Detail cache.
- Rank.
- Food history.
- Last-known recommendations with timestamp.
- Clearly unavailable-refresh state.
- Stale hours treated unsafe.
- Menu freshness handled separately.
- No fake freshness.

### 3.34 Accessibility completion across every rebuilt screen
- Screen-reader semantics.
- Large text.
- Low vision.
- Color-independent meaning.
- Motor accessibility.
- Reduced-motion alternatives.
- Map list equivalent.
- No swipe-only flows.
- Captions for video.
- Appropriate media descriptions.
- Dietary/allergy claims communicated with high honesty.

### 3.35 Full screen-state coverage
Every relevant screen still needs implementation/verification for:
anonymous, authenticated, loading, success, empty, partial data, stale,
offline, permission denied, low confidence, error, and relationship-
specific states.

### 3.36 Final legacy cleanup
- Remove dormant duplicate routes.
- Remove zero-caller compatibility adapters.
- Remove stale old product comments.
- Remove tests asserting superseded behavior.
- Remove dead navigation scaffolding.
- Do not remove anything before its replacement is live/tested.
- Update the traceability matrix with final implementation/test locations.

### 3.37 Final V1 end-to-end QA
Verify the primary loop:
`open → find → understand why → decide → act/save → visit → Rank → CRAVE improves`

And the first-week loop:
`cold start → initial evidence → better recommendations → visits → Rank/corrections → meaningful Taste Profile`

## 4. Explicitly blocked — never give Codex these as V1 implementation tasks

Keep these blocked unless explicitly promoted by a newer approved
canonical decision:
- Shared Craves
- Dish Rank
- voice Search
- full route-aware discovery
- personal food-history map
- full reservations/ordering integration
- taste-similarity people-recommendation feed
- visible social Rank beyond coarse opt-in highlights
- imported "Seen on social" dedicated Place Detail placement
- an expanded standalone Leaderboard

The Readiness Audit explicitly marks these OPEN / LATER / AUDIT REQUIRED.

## 5. Wave summary

- Waves 0-4: done, merged.
- Wave 5: Search + contextual Map.
- Wave 6: Craves intelligence.
- Wave 7: Place Detail + operational/dish/taste dependencies.
- Wave 8: Posting/private logging.
- Wave 9: Profile/Taste/Other Profile.
- Wave 10: Activity/Cold Start/Auth completion/Settings.
- Then: legacy retirement + full V1 certification.

## 6. Definition of Done (permanent regression gate, not a wave)

This is not implementation work — it is the standing verification gate
re-run after every major wave and again at V1 completion:
- backend compile/import
- backend `pytest`
- Alembic single head
- real-Postgres migration chain
- migration downgrade/re-upgrade
- frontend `tsc`
- full Jest suite
- conflict-marker guard
- dependency vulnerability scan
- CodeQL JS/TS
- CodeQL Python
- route/deep-link tests
- state tests
- accessibility checks
- visual QA against the relevant Screen Contract
- Railway deployment verification

A wave is not complete when code merely renders — it is complete when this
gate passes and the item's own acceptance criteria (in its screen contract)
are met, per `CRAVE_CODEX_IMPLEMENTATION_RULES_V2.md` §23.

## 7. Traceability

**Backward:** `CRAVE_CODEX_READINESS_AUDIT.md` (source of every named
blocker), `CRAVE_IMPLEMENTATION_MIGRATION_PLAN.md` (wave definitions and
migration doctrine this list is grouped by), `CRAVE_API_INTEGRATION_CONTRACTS.md`
(literal shape for every backend-capability item), all `CRAVE_SCREEN_CONTRACT_*.md`
files, `CRAVE_CODEX_HANDOFF_STATE.md`.

**Forward:** `CRAVE_REQUIREMENTS_TRACEABILITY_MATRIX.md` should be updated
as each item lands with its implementation/test location, per Migration
Plan §23's final cleanup gate.
