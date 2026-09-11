# Execution Brief — Waves 7-10 (2026-09-08)

> **Superseded for sequencing, 2026-09-11.** This doc's Wave 7→8→9→10
> *ordering* is historical — `docs/doctrine/CRAVE_FRONTEND_EXECUTION_ORDER.md`
> is now the authoritative frontend execution order (Foundation Gate →
> Place Detail proving slice → Feed/Decision → Search/Map propagation-only
> → Craves → Rank → Food Evidence/Add Spot → Profile/Taste/social cleanup →
> Auth/Settings/Activity completion → cross-app accessibility/E2E/release
> certification). Wave 7 below is complete and unaffected. This brief's
> **content** below each wave heading (the concrete findings on what's
> buildable vs. genuinely blocked, and the non-negotiable operating rules)
> remains accurate and still applies — read it for *what*, read the new
> doctrine doc for *when/in what order*. "Where to resume right now" at
> the bottom of this file is stale; ignore it in favor of the new doc's
> own "Next action."

Self-contained handoff for whichever Claude session picks up implementation
after Wave 6 (Craves intelligence, **COMPLETE** as of PR #219). Written so a
fresh session can resume without reconstructing scope from
`CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.5-3.37 from scratch — that doc
stays the canonical source of truth; this brief adds the concrete,
already-verified findings that doc doesn't have (what's actually buildable
today vs. genuinely blocked, and by what).

## Non-negotiable operating rules (carried from Wave 5/6)

- Read `AGENTS.md` and `.agent-bridge/PROTOCOL.md` first. Claim your wave in
  `.agent-bridge/STATE.md` before editing anything.
- One PR per outcome. Full local verification (`tsc --noEmit`, full Jest
  suite, backend `pytest` against a real local Postgres, Alembic
  single-head check) before every push, matching
  `CRAVE_MASTER_CODEX_REMAINING_WORK.md` §6's Definition of Done.
- Never fabricate a signal, a data field, or a "done" status. If a bullet
  in the master doc depends on data/infrastructure that doesn't exist,
  say so precisely (which section blocks it, why) rather than
  approximating with a heuristic — see the Craves §11 and Search §17
  doctrine corrections (PRs #219, and Search's own) for the exact pattern
  to follow: reclassify in the relevant Screen Contract, cite the real
  blocker, don't fake the feature.
- §4 of the master doc lists items **explicitly blocked for all of V1**,
  not just "not yet built": Shared Craves, Dish Rank, voice Search, full
  route-aware discovery, personal food-history map, **full reservations/
  ordering integration**, taste-similarity people-recommendation feed,
  visible social Rank beyond coarse opt-in highlights, imported "Seen on
  social" dedicated Place Detail placement, an expanded standalone
  Leaderboard. Do not implement any of these as a side effect of a wave
  below, even a scoped-down version.
- CodeRabbit: `@coderabbitai review` on every code PR; skipped
  automatically on docs-only PRs (repo has <10 stars).
- Merge only after all CI checks green (8 checks including default
  `CodeQL`, distinct from the custom `Analyze` jobs), verify the merged
  SHA via `git log origin/main`, unsubscribe from PR activity.

## Wave 7 — Place Detail relationship hierarchy

Source: `CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.5-3.10,
`docs/doctrine/CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md` (Draft, pending
audit — 532 lines, read in full before touching this screen).

**Already verified this session** (read `frontend/app/place/[id].tsx` in
full, 1196 lines, plus the relevant backend models):

- No relationship-state framing exists beyond a binary
  `visited`/`notes` toggle (`HitlistSave`-backed, lines ~737-786).
- `DecisionStrip` (`frontend/src/components/DecisionStrip.tsx`) is NOT
  used in this file — it hand-rolls its own `decisionStrip`/`whyFits`
  views (lines 482-570) instead, despite the component already being
  shared by Craves/Search/`PlaceCardCompact`.
- Primary CTA (lines 576-609) is binary-static: ranked → "Your score,"
  unranked → "I ate here." Never Reserve/Directions/Save-for-tonight.
- Report/correction actions already exist and are wired:
  `ReportPhotoSheet` (line 935), `ReportPlaceSheet` (line 942) →
  `backend/app/api/v1/routes/moderation.py`. Don't rebuild these.
- `VisitEvidence` (`backend/app/db/models/visit_evidence.py`) dedups by
  `(user_id, place_id, source, source_ref)`; `saves.py` always passes
  `source_ref=save.id`, so repeated "I ate here" toggles never create
  more than one row per save. **No visit-frequency signal exists
  anywhere** — `PlaceRanking` also has a unique `(user_id, place_id)`
  constraint, no revisit counter.
- No navigation call site threads a save/recommendation reason today:
  `craves.tsx`, `SearchScreen.tsx`, `MapScreenCore.tsx` all call bare
  `router.push('/place/${id}')`. `decision_role`/`craveRole`/
  `searchReason` are logged to analytics at the tap but discarded, not
  passed through.

**Buildable now, no production access needed** (do these):

1. Backend: `visit_evidence_for_place(db, user_id, place_id)` helper in
   `visit_evidence_service.py` — single-place lookup; only a batch
   version exists today (`craves.py`'s graduation query).
2. Backend: add nullable `reason_role`/`reason_source` columns to
   `HitlistSave`, settable optionally at save-creation
   (`POST /saves`) — persists "why you saved this" per contract §13.
   Migration, verified against local Postgres (same discipline as the
   `visit_evidence`/`place_reports` migrations this session).
3. Backend: add a real revisit counter — increment only on the
   `visited` **False→True** transition (never on repeated PATCH calls
   with `visited: true` already set), so "regular" is a genuine signal,
   not a fabricated one from data that doesn't support it.
4. Frontend: thread `reason_role`/`source` as nav params from
   craves/search/feed into `/place/[id]`, and read them there.
5. Frontend: rebuild the top-of-page around the four relationship modes
   (never visited / considering tonight / visited-not-regular /
   regular) using (1)-(4) above.
6. Frontend: swap the hand-rolled `decisionStrip`/`whyFits` views for
   the shared `DecisionStrip` component.
7. Frontend: adaptive primary CTA ladder per contract §11 — Directions
   → Save-for-tonight → Save, or Quick-Take/"Rank it"/"Your rank" once
   visited. **Omit Reserve** (see blocked, below).
8. Stop persuading after a confirmed visit — conditional render using
   data already available.

**Genuinely blocked — do not attempt, document instead:**

- **Reserve as a CTA rung.** No reservation-provider integration exists
  anywhere in the app, and §4 of the master doc explicitly blocks "full
  reservations/ordering integration" for all of V1. Omit this rung
  entirely from the CTA ladder; don't stub a fake "Reserve" button.
- **Why-This-Fits' 4-action taste-correction vocabulary** (Not true /
  Doesn't matter / Less / More) — needs the Gate 2 taste graph (§3.8),
  which doesn't exist. Contract §22/§12 already name this as an
  unresolved dependency; don't build a UI with nothing real behind it.
- **§3.6-3.10 foundational systems** (operational open/closed data,
  Dish Intelligence, the taste graph itself, menu personalization, media
  provenance) — these are why Place Detail's own contract status is
  YELLOW, not GREEN, and they are multi-PR systems in their own right,
  several requiring live external data feeds this environment doesn't
  have production access to verify end-to-end. Wave 7's 8 bullets
  (§3.5) do not require these to be complete first — they're scoped
  narrowly enough to build on existing data, per the breakdown above —
  but don't let "finish Wave 7" drift into silently also building §3.6-
  3.10, and don't claim Place Detail's overall contract status moves to
  GREEN just because Wave 7's own bullets are done.

**Suggested split:** one backend PR (items 1-3), one frontend PR (items
4-8, building on the backend PR), one docs-only PR correcting the
contract's status section to reflect what shipped and what's still
blocked (mirroring PRs #219 and the Search §17 correction).

## Wave 8 — Native Posting / Private Logging composer

Source: §3.11-3.14. Not yet scoped against current code this session —
read `docs/doctrine/CRAVE_SCREEN_CONTRACT_*` for whichever contract
covers posting (check `CRAVE_TARGET_SCREEN_REGISTRY.md` if no dedicated
contract exists yet; one may need drafting first, following the same
audit process used for Search/Craves this session) before writing code.

Key shape from the master doc:
- Unified composer flow: `capture → restaurant confirmation → dish
  confirmation → quick take → caption → visibility`.
- Private logging and public/social posting are separate outcomes, not
  one flow with a visibility toggle bolted on.
- Media required for public/follow-scope; not required for private log.
- Visibility (private / approved-follow / public) cannot be silently
  defaulted — always an explicit choice.
- Backdating support; restaurant search/manual missing-place path; dish
  confirmation only where Dish Intelligence capability exists (likely
  not yet — check Wave 7's outcome first).
- Backend: upload/publish/private-log endpoints, idempotency/retry
  protection, correct post-commit evidence emission, no half-created
  evidence on failed upload.
- Migrate `record-video` and `add-spot` into the new composer only
  after parity is proven; preserve old deep links during transition;
  retire only after zero callers remain (§3.13/3.14 — don't delete
  early).

Likely **not** blocked by missing production data the way Wave 7's
foundational items are — media upload/storage already works today
(existing photo/video posting features this session found while
auditing Place Detail's media actions). Verify that assumption before
starting: confirm the existing upload pipeline (whatever backs today's
photo/video submission) is reusable rather than assuming.

## Wave 9 — Profile / Taste Profile / Other User Profile

Source: §3.15-3.19, §3.28.
- Profile: compact Rank status/link only (not full Rank), real taste
  identity summary, food history, user posts, constrained/automatic
  tagline (not a free-text bio), remove old `friends-feed` entry point
  (§3.27 — full retirement procedure, don't just hide it), no vanity
  follower counts, privacy defaults preserved.
- Taste Profile: inspectable taste model UI, "Still learning" when
  confidence is insufficient, 4-action corrections (Not true / Doesn't
  matter / Less / More — **same Gate 2 dependency flagged as blocked in
  Wave 7**; this entire section is likely blocked on the same taste
  graph until §3.8 lands), dietary/allergy/religious/ethical hard
  constraints, novelty preference, never fabricate a trait to fill the
  screen.
- Three distinct personalization controls (§3.17): pause
  personalization / reset current recommendations / reset inferred
  taste while preserving factual history — these must stay separate
  actions, never one "Reset everything" button.
- Other User Profile: no public-by-default sensitive taste info, only
  owner-approved coarse Rank highlights, taste compatibility only on
  deliberate navigation (§3.19 — compare only approved/shared coarse
  data, no scraping, no follower-influenced compatibility).
- `profile-setup.tsx` retirement/split (§3.28): separate identity setup
  from food calibration, move calibration into the canonical cold-start
  flow (Wave 10).

**Flag before starting:** most of Taste Profile's real content depends
on the Gate 2 taste graph existing. Confirm whether §3.8 has landed (by
Wave 7 or a dedicated foundational PR) before claiming this wave — if
not, the honest scope for Wave 9 is the Profile screen itself (compact
Rank, food history, posts, retirement work) with Taste Profile's UI
built against a "Still learning" / low-confidence state throughout,
not fabricated trait data.

## Wave 10 — Activity Inbox / Cold-Start / Auth completion / Settings

Source: §3.20-3.26, §3.33 (offline/stale-state — shared dependency with
Search's §17, don't build twice, see cross-reference in the master doc).
- Activity Inbox (§3.20): real screen + event source/API, deep links,
  follow requests, Rank reminders, reservation/reopening events **only
  where those capabilities exist** (reservations are blocked per §4 —
  omit that event type entirely, don't stub it), no generic
  re-engagement notifications.
- Cold-start calibration (§3.21) + anonymous recommendation bootstrap
  (§3.22) + anonymous-to-account migration (§3.23): anonymous users
  reach a useful Feed before account creation, dietary/allergy
  disclosure only mandatory step, no onboarding Rank duels, defensible
  city-level baseline with honest lower-confidence labeling.
- Auth-gate call-site migration (§3.24): finish centralizing Save/Rank/
  Post/Follow auth gates — check how much of this is already done
  post-Wave 6 (Craves' `AuthSheet` usage) before assuming it's all
  outstanding.
- Settings/Privacy (§3.25) + privacy lifecycle backend (§3.26): export/
  delete account, taste-reset controls (reusing §3.17's three distinct
  operations, not inventing new ones), destructive actions visually
  separated.
- Offline/stale-state layer (§3.33): this is the SAME app-wide
  `NetInfo`/connectivity-detection gap already found and correctly
  deferred in the Search Screen Contract's §17 correction this session
  — build it once here if picked up, and it retroactively unblocks
  Search's own "Stale" state-coverage row and Craves' equivalent, no
  contract rewrite needed on either.

## After Wave 10 — do not skip

§3.27/3.29-3.32/3.34-3.37: legacy route retirement (only after zero
callers — verify with an actual search, not an assumption), leaderboard
audit (**AUDIT REQUIRED status, not free implementation territory** —
read §3.29 verbatim before touching it), cache/analytics migrations,
deep-link migration table, accessibility completion across every
rebuilt screen, full screen-state coverage, then the final V1 end-to-end
QA pass verifying both stated user loops. Re-run §6's Definition of Done
gate at the end of every wave and again at full V1 completion — it is
the actual finish line, not "the code renders."

## Where to resume right now

Stale as of 2026-09-11 — Wave 7 finished long ago. See the superseding
notice at the top of this file: `.agent-bridge/STATE.md`'s top section and
`docs/doctrine/CRAVE_FRONTEND_EXECUTION_ORDER.md`'s own "Next action" are
the current source for where to resume.
