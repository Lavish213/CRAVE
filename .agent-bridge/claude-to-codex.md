# H-20260909-food-evidence-media-drop

Status: blocked -- not on a missing credential, on a product/architecture
decision only a human or Codex with more context should make. Everything
below is a finding plus concrete options, not a diff.
Owner: Claude (finding) -> Codex (scope + implement, or escalate to the
human if the options below aren't an acceptable tradeoff)
Branch: none from me -- no code changed for this item
Base SHA: c8abbc55d47d75838fbeae9f9d597fbeb9f6b62c (`origin/main`, current
as of this handoff)
Commit SHA: none
Allowed next files: `frontend/app/food-evidence.tsx`, `frontend/app/
add-spot.tsx`, `frontend/src/api/upload.ts`, `frontend/src/api/nearby.ts`,
`frontend/src/stores/videoQueueStore.ts` (read-only reference for the
existing local-queue-then-upload pattern -- don't duplicate it blind,
see below), plus whatever new backend surface option C below would need.
Do not touch `frontend/app/taste-profile/[userId].tsx` or its test file
-- that's a separate, already-merged fix (PR #236), unrelated to this.

## Outcome

Found during a full app-wide screen-by-screen audit (every route in
`frontend/app`, one screen at a time, same rigor as the earlier Search
subsystem audit). This is the single most severe finding: the primary
"+" FAB, reachable from every tab via `(tabs)/_layout.tsx`'s
`recordAction` button (`router.push('/food-evidence')`), lets a user
take a photo, choose a photo, or choose a video from their library --
then "Continue" does nothing but `router.push('/add-spot')`. The
captured `{ kind, uri }` is local `useState` in `food-evidence.tsx` and
is never passed as a nav param, queued, or uploaded. `add-spot.tsx` has
no idea any media was ever selected. Confirmed via grep: no
`foodEvidence`/pending-media store or API client function exists
anywhere in `frontend/src`. The screen's own copy ("Restaurant
identification and the private-or-post decision come next") promises a
continuation that isn't implemented. Net effect: a user captures real
food evidence, taps the one visible next step, and it is silently
discarded with no error, no warning, nothing.

## Why this isn't a one-line fix

Both existing upload paths in this codebase require a resolved
`place_id` **at the moment the upload is requested**:
- Photo: `frontend/src/api/upload.ts`'s `requestUpload()` takes a
  mandatory `place_id` in `UploadRequestPayload` (backend:
  `POST /api/v1/upload/request`).
- Video: `frontend/src/stores/videoQueueStore.ts`'s `recordVideo()`
  takes a `placeId` up front too (it's the queue key).

`food-evidence.tsx` captures media *before* a place is identified --
its own header text says so explicitly. `add-spot.tsx`'s nearby search
(`searchNearby()`) returns two kinds of result:
- `already_in_crave: true` -> a real `place_id` exists immediately.
- `already_in_crave: false` -> tapping "This is it" calls
  `confirmNewSpot()`, whose response (`ConfirmNewSpotResponse`) only
  returns a `candidate_id`, **not** a `place_id` -- it creates a
  `DiscoveryCandidate` for the normal async promotion pipeline, not a
  `Place` row. There is no place to attach media to yet on this branch,
  and promotion may not happen at all (or not soon).

So this isn't "thread a param through" -- it's a genuine gap in the
upload contract for exactly the candidate-not-yet-a-place case.

## Options (pick one, or propose a better one -- don't guess silently)

**A -- narrowest, recommended if a fast fix matters more than full
coverage:** Pass `{ mediaUri, mediaKind }` as route params from
`food-evidence.tsx` to `/add-spot`. Wire the upload only on the
`already_in_crave: true` branch (a real `place_id` already exists at
that point) -- call `requestUpload`/`uploadToSignedUrl`/`confirmUpload`
for a photo, or the video queue's existing flow for a video. On the
`already_in_crave: false` branch (brand-new candidate), do **not**
silently drop the media either -- show the user an explicit message
("This place needs to be confirmed first -- come back and add a photo
once it's live") rather than pretending it uploaded. This ships real
value for the common case (identifying an existing place) and turns
the remaining gap into an honest, visible limitation instead of a
silent one.

**B -- fuller coverage, more backend work:** Add a new backend
endpoint/field to attach pending media to a `DiscoveryCandidate` at
confirm time (e.g. `POST /api/v1/nearby/confirm` accepts an optional
media reference, stored and later transferred to the `Place` row if/
when promotion happens). Real feature work, needs its own design pass
on the candidate/promotion pipeline -- do not start this without
scoping it as its own task first.

**C -- reframe the screen instead of the plumbing:** If neither A nor B
is worth the engineering cost right now, the honest short-term fix
might be removing the "Continue" button's false promise entirely (e.g.
disable it with a "coming soon" state, matching this app's own existing
convention for genuinely unbuilt controls -- see `settings.tsx`'s "Rate
CRAVE" row) until a real continuation exists, rather than shipping a
button that silently eats the user's photo/video. This is a product
call, not an engineering one -- flag it to the human rather than
deciding unilaterally if A/B both seem like too much scope right now.

## Known gaps / risks

- This entry is a finding + options, not a verified fix. Whichever
  option is picked still needs its own `tsc --noEmit` + full frontend
  suite pass before merging, same discipline as every other PR in this
  repo.
- Option A still leaves a real (now honestly-surfaced, not silent) gap
  on the new-candidate branch. Don't let that get re-classified as
  "fixed" without also closing that branch, or explicitly deferring it
  in `STATE.md` the way `hours`/outdoor-seating was deferred before PR
  #229 closed it.
- Claude has no Railway/production DB access and did not check whether
  `DiscoveryCandidate`'s promotion pipeline (relevant to option B) has
  any existing hook that would make this easier or harder than it looks
  from the frontend alone -- verify against the actual backend model/
  service before committing to option B's scope.

## Next action

Read `frontend/app/food-evidence.tsx` and `frontend/app/add-spot.tsx`
in full, confirm the analysis above against current code, then either:
(1) implement option A (recommended for a same-day fix) with tests
covering both the already-in-CRAVE upload path and the new-candidate
honest-limitation message, or (2) if A/B/C all seem wrong, post a
clear status update in `.agent-bridge/codex-to-claude.md` or ask the
human directly rather than leaving the FAB silently broken.

---

# H-20260909-menu-canary-production-approval

Status: ready-for-review -- this is an approval, not a diff
Owner: Codex (execution) -- Claude relaying the human user's explicit
approval below
Branch: none from me
Base SHA: 4e3def0f5bd7de78097a3946d90c621e64a1e311 (`origin/main`,
current as of this approval)
Commit SHA: none
Allowed next files: none from me on this -- run the canary itself, then
record the outcome per your own item 1's "Required deliverables" (see
`docs/CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`).

## Outcome

The human user (repo owner) has **explicitly approved** running the real
ten-place production menu backlog canary
(`backend/scripts/run_menu_backlog_canary.py --run --confirm-count 10`)
that was reported as passed-preview-but-stopped, pending approval,
because it publishes extracted menu data immediately with no automatic
rollback.

Exact approval given, verbatim intent: approve running it, on the
condition that **all 10 outcomes get reviewed immediately after
publish**, not just trusted silently -- same stop-on-contamination
posture already established for every other canary in this handoff
thread (cross-venue contamination, missing provenance, low-quality
publish, paid-provider traffic, or more rows touched than reviewed all
still mean stop, not proceed).

## Known gaps / risks

- Claude has no Railway/production DB access and cannot run or verify
  this canary directly -- this entry is a relay of the human's decision,
  not independent verification of the canary's own correctness. The
  code-level safety properties (preview-first, hidden/non-primary
  staging, no automatic promotion) were reported by Codex's own prior
  message, not re-verified here.
- This approval covers exactly this one ten-place run at the reviewed
  scope. It is not a standing approval for a larger batch or a repeat
  run without a fresh preview -- re-confirm before widening.

## Next action

Run the approved ten-place canary now. Review every one of the 10
outcomes immediately after publish (not on a delay) and manually revert
any row that shows cross-venue contamination, missing provenance, a
low-quality publish, or paid-provider traffic -- exactly the stop
conditions this handoff thread has used throughout. Record the actual
outcome (which places, pass/fail per place, any manual reverts) back in
`.agent-bridge/STATE.md` or `DECISIONS.md` so this run has a durable
record, matching this repo's own convention for closed-out canaries
(see the Oakland Overture canary's own write-up as the template).

---

# H-20260909-osm-hours-seating-backfill

Status: blocked -- missing credential (Railway/production Postgres access),
not missing code. Everything below is implemented, tested, and merged;
it just has never been run against the real database.
Owner: Claude (handoff) -> Codex (execution)
Branch: none needed -- this is a one-off data operation against an
already-merged script, not a new diff. Only record the run's outcome
afterward (see Next action) if you want that durable, which would be a
small follow-up commit.
Base SHA: c3953c208505bef3b5dbefa6fe013aea78cc9021 (`origin/main`,
current as of this handoff -- confirmed via `git log origin/main`)
Commit SHA: none from me on this handoff
Allowed next files: none from me further on this. If you record the
run's outcome, the natural spot is `.agent-bridge/STATE.md`'s "Search/
Map V1.5 design-audit fixes" section (already has the PR #229 entry to
append to) or `DECISIONS.md` -- whichever this repo's convention favors
for a completed-execution note.

## Outcome

PR #229 (merged onto `main` at `df92429`, this handoff's base commit is
one further merge past it) added `backend/scripts/
backfill_osm_hours_and_seating.py` -- a script that retroactively writes
`hours`/`outdoor_seating` `PlaceClaim`s for OSM-sourced places that were
already promoted to `Place` rows *before* `promote_service_v2.py`
learned to read those two OSM tags. It reads only data already sitting
in `discovery_candidates.raw_payload` (the full OSM tags dict, fetched
long ago by `osm_overpass.py`) -- **no new network fetch, no re-scrape,
free and instant** against what's already in Postgres. It has never
been run against production because this Claude session has no
Railway/Supabase/Postgres credential -- confirmed and re-confirmed
multiple times this session; this is a real blocker, not something
routed around.

Fully verified locally: 4 passing tests in `backend/tests/
test_backfill_osm_hours_and_seating.py` (writes claims+truths correctly,
idempotent on a second run, skips non-OSM sources, `--dry-run` writes
nothing), full backend suite green (1110 passed, 2 skipped) against a
freshly reset local Postgres schema.

## Exact directions to run it

1. Clean worktree, current `origin/main` (`git log --oneline -3` should
   show `c3953c2` or later -- fetch first if not).
2. Set `DATABASE_URL` to production's real Postgres connection string
   (Railway env var). **Never print, log, paste, or commit this value
   anywhere** -- including into this file, a commit message, or a PR.
3. Dry run first -- writes nothing, just reports scope:
   ```
   cd backend
   python scripts/backfill_osm_hours_and_seating.py --dry-run
   ```
   Logs `candidates_touched`, `claims_written`, `places_affected`.
4. Sanity-check those numbers before proceeding: `claims_written`
   should be a real fraction of total OSM-sourced promoted places, not
   ~0 (nothing to backfill -- suspicious if OSM ingestion has run at
   all) and not ~100% (OSM tag coverage for these two fields is
   genuinely partial -- most nodes don't carry `opening_hours`/
   `outdoor_seating`). If either extreme shows up, stop and investigate
   before writing.
5. Run for real (omit `--dry-run`):
   ```
   python scripts/backfill_osm_hours_and_seating.py
   ```
   Idempotent -- safe to re-run if interrupted or after a fresh OSM
   ingest/promote cycle adds new candidates; already-written claims are
   skipped on any later pass.
6. Spot-check a handful of real place IDs afterward: `GET /place/{id}`
   should return non-null `hours_status`/`outdoor_seating` for a place
   you can independently confirm has real OSM hours data (or query
   `place_truths` directly for `truth_type IN ('hours', 'outdoor_seating')`).
   Also worth confirming the Place Detail screen's decision-strip chip
   (🟢/🔴 hours, 🌤️ outdoor seating) actually renders for one such place
   in the running app, not just in the API response.

## Known gaps / risks

- This Claude session has no Railway/Supabase/production Postgres
  access -- cannot run this itself or verify a real production count.
  That is the entire reason this is a handoff.
- Only OSM-sourced (`source == "osm"`) already-promoted candidates are
  touched, by design -- Overture and other sources aren't read for
  these two fields since only OSM's tag vocabulary was verified
  reliable for them (see PR #229's description for why Google
  Places/Yelp/Foursquare were ruled out too: all need a new account/API
  key only a human can authorize, and Google's ToS additionally forbids
  long-term caching of place data).
- Coverage will be partial after this runs -- a place with neither OSM
  tag simply gets no claim. That's correct behavior (no fabricated
  data), not a bug to chase further.
- No schema/migration risk: this only writes to the existing
  `place_claims`/`place_truths` tables via the same code path
  `promote_service_v2.py` already uses for every other automated claim.

## Next action

Claim this in `STATE.md` per protocol (owner, base SHA, no new branch
needed since no code changes are expected) before running anything.
Run the dry-run first, then the real run, then record the final counts
somewhere durable (`STATE.md` or `DECISIONS.md`) so a future session
doesn't re-run this blindly or re-flag it as still-needed.

---

# H-20260907-population-coverage-canaries

Status: information-only -- an inventory, not an execution authorization
Owner: Claude (handoff) -> Codex (execution)
Branch: none from me -- this is a task handoff, not a diff
Base SHA: c34a9dd7492f59918ee058fce615dfe17dba0f90 (main, current as of
this update)
Commit SHA: none
Allowed next files: none from me further on this topic. This does
**not** mean Codex has zero scope -- per `.agent-bridge/PROTOCOL.md`,
Codex must claim exactly one bounded item below in `STATE.md` first
(owner, a fresh branch off current `origin/main`, base SHA, the exact
files/scripts that item touches, and a verification plan) before
implementing or running anything. Do this from a clean worktree, not a
stale local checkout -- an internal audit of this handoff found a local
checkout on `claude/project-grade-systems-review-4ot7d0` sitting 321
commits behind `origin/main` with uncommitted changes; never claim or
execute from a checkout like that.

## Outcome

Bundling every still-open item on the production data-coverage lane
(needs Railway/Supabase access, which this Claude session does not
have) into one place, per the user's explicit ask to consolidate rather
than let these sit scattered across `CRAVE_STATUS.md`,
`docs/SCHEDULER_WORKER_ROLLOUT.md`, and
`docs/CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`. Nothing
below is new work I invented -- every item already exists in those docs;
this is a consolidation and a re-confirmation that none of it has moved
since 2026-09-02 (checked `git log --all --since=2026-09-02` for any
canary/population/scheduler commit -- none found).

**Read first, in order, before touching production:** `AGENTS.md`,
`.agent-bridge/PROTOCOL.md`, `CRAVE_STATUS.md` (`## Needs your action`
and `## What's solid right now` -> population baseline), `docs/
POPULATION_READINESS.md`, `docs/SCHEDULER_WORKER_ROLLOUT.md`, `docs/
CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md` (Track 2 has
the full phased procedure -- Phase A read-only baseline through Phase F
widen-on-evidence; this handoff does not repeat those operating rules,
it only says which phase each item is at). **Re-measure the baseline
before acting on any of it** -- the counts below are historical from
2026-09-02 and may already be stale.

### 1. Menu backlog canary (Track 2, Phase D) -- next concrete step ready
- Candidate pool: 13,128 active places with a website but no
  materialized menu (as of 2026-09-02; re-measure via
  `python scripts/menu_coverage_report.py`).
- Tool: `backend/scripts/run_menu_backlog_canary.py` -- preview-only by
  default; `--place-ids` (comma/newline list) or `--place-ids-file`,
  then `--run --confirm-count N` to execute, where N must exactly equal
  the reviewed ID count.
- History: the one real attempt so far (a place called Itani) surfaced
  duplicate/contaminated rows and was reversibly quarantined, not
  promoted -- read that finding in the agent-bridge history before
  retrying. At most 10 reviewed targets per run; stop on any cross-venue
  contamination, missing provenance, low-quality publish, paid-provider
  traffic, or more rows touched than reviewed.

### 2. Free image acquisition canary (Track 2, Phase E) -- needs a fresh source attempt first
- Candidate pool: 7,816 active, website-backed places with zero image
  rows (as of 2026-09-02).
- Tool: `backend/scripts/run_free_image_canary.py` -- `--place-ids`
  (required, comma/newline, max ~10), preview by default, `--run
  --confirm-count N` (N = de-duplicated ID count) to stage. Staged rows
  are always hidden/non-primary; only a separate reviewed promotion step
  can make one public.
- History: the existing image worker is explicitly *not* safe to use as
  this canary -- it can fall back to paid Google and publishes
  candidates immediately, both forbidden here. The one static-extraction
  attempt so far found zero free candidates on two sites -- confirmed
  low recall as the real blocker, not bad source data. Needs a different
  extraction approach (JSON-LD/provider metadata on a fresh stratified
  cohort per Phase B) before the next attempt, not a retry of the same
  method.

### 3. `image_processing_recovery` real reclaim-logic canary -- blocked on empty queue so far
- The job has run in production multiple times but every run hit an
  empty queue, so only *execution* was proven, not the actual reclaim
  behavior (an image stuck mid-processing getting correctly reclaimed).
- PR #115 (merged) proves the reclaim logic locally against
  `backend/tests/test_image_processing_recovery.py`. The production
  proof still needs Codex's DB access to either wait for or manufacture
  a real stuck-image scenario and confirm the job reclaims it correctly
  end-to-end.

### 4. Video canary -- needs a seeded device pass, not another config change
- Every natural production run of `video_processing` so far has hit an
  empty batch (job executes and exits cleanly with nothing to do). Real
  R2 transfer, ffmpeg encoding, and classifier quality on a genuine
  uploaded video have never been proven in production.
- This specifically needs a real device recording -> upload -> R2 ->
  scheduler -> ffmpeg -> classifier chain with an actual video, which
  means either a seeded test upload against the real R2 bucket or a
  physical-device recording session -- not something achievable by
  widening the scheduler allowlist further.

### 5. Second-city Overture population canary (A7 broader source discovery)
- The Oakland canary (`docs/OVERTURE_ENTITY_REVIEW_2026-08-30.md`) is
  fully closed out: 10 staged candidates individually reviewed, 1 new
  place promoted, 3 matched to existing places, 1 alias resolved, 5
  rejected as stale, 3 existing places found stale and deactivated.
- Tool: `backend/scripts/run_overture_canary.py --city-slug <city>
  --limit 10` to preview (read-only default), then `--stage --batch-id
  <id> --confirm STAGE_OVERTURE` to stage as blocked
  `DiscoveryCandidate` rows (never user-visible pre-review), and
  `--rollback-batch <id> --confirm ROLLBACK_OVERTURE` if a staged batch
  needs to be pulled while still unresolved.
- **Explicitly not a copy-paste of Oakland**: pick a genuinely different
  city, and every staged row needs its own existing-match/alias/stale/
  genuinely-new review the same way Oakland's did, using
  `OVERTURE_ENTITY_REVIEW_2026-08-30.md` as the template, not a
  rubber-stamp. Watch specifically for the entity-matcher bug already
  found and fixed once (a shared brand website across chain locations
  being treated as proof of identical physical location).

### 6. B1 steps 2/4 -- real image fetch + hand-labeling -- **not execution-ready, needs scoping first**
- Untouched since the brief was written. Needs production access to even
  start; no local/sandbox proxy exists for this one. No further detail
  to add beyond `CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`
  Phase C/Phase E's classification-vs-acquisition distinction --
  `run_phase3_image_backfill.py` is classification only, not a source of
  new images.
- Unlike items 1/2/5, this is an umbrella item, not a runnable canary:
  it has no exact cohort, no command, no acceptance criteria, and no
  rollback plan. Do not claim this in `STATE.md` as-is -- first do a
  short scoping pass (pick a cohort per Phase B's stratification list,
  name the exact extraction method, define stop/rollback conditions)
  and write that up as its own addition to this file, *then* claim it.

## Known gaps / risks
- All six items above need Railway/Supabase production DB access this
  Claude session does not have -- that is the entire reason this is a
  handoff rather than something completed directly.
- Every number cited above is historical (2026-09-02) and explicitly
  requires re-measurement before any write action, per the brief's own
  rule: never claim a coverage percentage change without a fresh
  before/after query on the same denominator.
- None of this blocks or is blocked by the Wave 5/6 product-implementation
  track below -- fully independent lanes, no shared files.

## Next action
Before executing anything: (1) work from a clean worktree checked out
from current `origin/main`, not a stale local branch; (2) re-measure
the relevant baseline read-only first (`menu_coverage_report.py` etc.)
-- every count in this file is a historical 2026-09-02 snapshot, not
current truth; (3) claim exactly one bounded item in `STATE.md` per
`PROTOCOL.md` (owner, branch, base SHA, locked files, verification
plan) before implementing or running any script.

Then pick one item at a time, each as its own PR per
`CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`'s "Required
deliverables" list (baseline evidence, extractor fix, canary evidence,
image promotion, and any scheduler expansion all stay in separate PRs).
Item 1 (menu backlog canary) or item 5 (second-city Overture) are the
most concretely actionable next steps; items 3/4 are blocked on either a
real stuck-image/real-device scenario occurring or being deliberately
staged; item 6 is explicitly not claimable yet -- scope it first (see
above).

---

## Separate, unrelated finding -- not this handoff's scope, flagging only

Four of *my own* (Claude-authored) PRs are still open and stale, none
of them Codex's responsibility, but worth a rebase-or-close decision by
whoever owns this repo's PR queue: #128 (`place-issue-reporting` --
a real, fully-tested backend+migration+frontend feature, looks genuinely
mergeable after a rebase, not superseded by anything since), #127
(`project-grade-systems-review-4ot7d0` -- small camera-failure-toast +
dead-control cleanup, likely still valid), #147 (`design-log-round-2`
-- docs-only, likely still valid), #145 (`state-housekeeping-2026-09-06`
-- STATE.md cleanup, now fully superseded by this session's own STATE.md
rewrites; safe to just close). All four predate `main`'s current head by
enough commits that GitHub reports their merge state as dirty/unknown.

---

## Wave 5 Search Screen Contract certification -- COMPLETE, compacted

Certified against `docs/doctrine/CRAVE_SCREEN_CONTRACT_SEARCH.md` across
PRs #190-#194 (CodeQL fix, Reason Block, zero-state/zero-result
contract completion, touch-target + doctrine corrections, canonical
docs update). Merged main SHA `b213f55`. Wave 5's contextual-Map
plumbing has one small open item (direct-mode Map ranking source, see
`CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.3) -- independent, does not
block Wave 6. Full detail in that same remaining-work doc and
`.agent-bridge/STATE.md`; nothing further needed from Codex on this
topic unless picking up the §3.3 item or Wave 6 (Craves intelligence).

---

## Older, still-open item (compacted, not superseded)

**H-20260906-sentry-production-verification-checklist** — status
unchanged: `docs/SENTRY_PRODUCTION_VERIFICATION.md` (3-proof runbook)
still needs someone with actual Railway + Sentry dashboard access to
run it; neither agent can from a repo-only session. Independent of
everything above — no shared files, nothing blocks on it.
