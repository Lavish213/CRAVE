# Claude execution brief: resume population coverage (menus, photos, second city)

Date: 2026-09-07
Audience: **any Claude session that has verified Railway/Supabase/Postgres
production access** — this could be Codex, a different Claude Code Remote
session, or a future session in this same project once that access exists.
The session that wrote this (repo-only, no Railway/DB access) could not run
any of it directly; this document exists so the next session that *can*
doesn't have to reconstruct the plan from five scattered docs.

## 0. Before you touch anything

1. Confirm you actually have the access this requires: a `DATABASE_URL`
   pointed at the real production Postgres (via Railway reference variables,
   `railway run`, or a securely obtained connection string — never paste the
   raw value into chat or a commit), and Railway dashboard access for
   anything this doc says needs it.
2. **Do not reuse a stale local checkout.** Start from a clean worktree:
   `git fetch origin main && git checkout -b <your-branch> origin/main`.
   An earlier audit of this same workstream found a local checkout 321
   commits behind `origin/main` with uncommitted changes — never claim or
   execute from something like that.
3. Read, in this order: `AGENTS.md`, `.agent-bridge/PROTOCOL.md`,
   `.agent-bridge/STATE.md` (current state/ownership),
   `.agent-bridge/claude-to-codex.md` (the live handoff this doc
   consolidates and supersedes for execution purposes — read it too, it has
   the same six items with slightly different framing),
   `CRAVE_STATUS.md`'s population-baseline section, `docs/
   POPULATION_READINESS.md`, `docs/SCHEDULER_WORKER_ROLLOUT.md`, `docs/
   CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md` (the original,
   fuller Track 2 procedure this doc summarizes and updates).
4. **Claim exactly one item below in `.agent-bridge/STATE.md`** — owner,
   branch, base SHA, the exact files/scripts this item touches, and a
   verification plan — before implementing or running anything, per
   `PROTOCOL.md`. Do not claim more than one at a time.
5. **Re-measure the baseline read-only first**, every time, before any
   write action. Every count in this document and in `CRAVE_STATUS.md` is a
   historical snapshot (last taken 2026-09-02) and may already be stale:

   ```bash
   cd backend
   python scripts/menu_coverage_report.py
   python scripts/menu_coverage_report.py --city-slug <city>
   ```

   Produce equivalent read-only image counts using `CRAVE_STATUS.md`'s own
   definitions (active-place denominator, public image, primary image,
   known website, website/no-public-image). Save sanitized output in a
   dated evidence doc. Never expose connection strings or tokens.

## 1. Non-negotiable operating rules (apply to every item below)

These are already-approved product/safety decisions, not open questions —
do not relitigate them mid-canary:

- No Google Places, paid LLM extraction, Bright Data, Firecrawl Cloud,
  Apify, proxy services, or any metered fallback in the free-source track.
- Respect `robots.txt`, source terms, rate limits, copyright, and
  provenance. Never bypass CAPTCHAs, access controls, TLS fingerprints, or
  anti-bot systems.
- Never hotlink unknown third-party images. Only stage permitted
  official-site/provider media with source and license/provenance
  evidence.
- Never enable recurring `menu_enrichment`, `image_ingestion`, discovery,
  scoring, ranking, OSM, or Overture jobs as a shortcut for a canary.
  Scheduler expansion is always its own separate production/security PR.
- New image rows remain hidden/non-primary until separately reviewed.
  Suspicious menus remain unpublished or quarantined.
- A canary with zero useful results is valid evidence, not permission to
  widen the batch. Widen a cohort (3-5 → 10 → 25) only after the prior one
  showed zero contamination, complete provenance, no paid calls, and
  stable service health.
- Always report absolute counts and percentages, before/after, same
  denominator:

  ```text
  menu:       before_count / active_places = before_pct
              after_count  / active_places = after_pct
              net +count, +percentage_points
  ```

  Never extrapolate a small canary into a catalog-wide promise. If the
  denominator changes, say so and compute a comparable cohort instead.
- One PR per outcome: baseline evidence, each extractor fix, each canary's
  evidence, any image promotion, and any scheduler expansion all stay in
  separate PRs. Never bundle two of these together.

## 2. The six items already scoped and ready to claim

These come from `.agent-bridge/claude-to-codex.md`'s
`H-20260907-population-coverage-canaries` handoff — full detail lives
there; this is the condensed version with exact commands.

### 2.1 Menu backlog canary — most concretely actionable
- Pool: ~13,128 active places with a website but no materialized menu (re-measure first).
- Preview, then execute only after reviewing the exact set:
  ```bash
  cd backend
  python scripts/run_menu_backlog_canary.py --place-ids-file /tmp/reviewed-menu-canary.txt
  python scripts/run_menu_backlog_canary.py \
    --place-ids-file /tmp/reviewed-menu-canary.txt \
    --run --confirm-count N
  ```
- History: one real attempt (a place called "Itani") surfaced
  duplicate/contaminated rows and was quarantined, not promoted — read that
  finding in agent-bridge history before retrying the same cohort. Max 10
  reviewed targets per run. Stop on cross-venue contamination, missing
  provenance, low-quality publish, paid-provider traffic, or more rows
  touched than reviewed.

### 2.2 Free image acquisition canary — needs a fresh extraction approach
- Pool: ~7,816 active, website-backed places with zero image rows.
- ```bash
  cd backend
  python scripts/run_free_image_canary.py --place-ids id-1,id-2
  python scripts/run_free_image_canary.py --place-ids id-1,id-2 --run --confirm-count N
  ```
- The existing image worker is **not** a safe substitute — it can fall
  back to paid Google and publish immediately, both forbidden here. One
  static-extraction attempt already found zero free candidates on two
  sites (confirmed low recall as the real blocker). Try JSON-LD/provider
  metadata extraction on a fresh stratified cohort (Phase B below) instead
  of repeating static HTML scraping.

### 2.3 `image_processing_recovery` real reclaim-logic proof
- Every production run so far hit an empty queue — only *execution* is
  proven, not the actual reclaim behavior. `backend/tests/
  test_image_processing_recovery.py` (PR #115) proves the logic locally.
  This item is: wait for, or deliberately stage, a real stuck-image
  scenario in production and confirm the job reclaims it correctly.

### 2.4 Video canary real device/R2 proof
- Every natural run of `video_processing` has hit an empty batch. Real R2
  transfer, ffmpeg encoding, and classifier quality on a genuine uploaded
  video have never been proven in production. Needs a seeded test upload
  against the real R2 bucket or a physical-device recording session — not
  another scheduler config change.

### 2.5 Second-city Overture population canary
- Oakland is fully closed out (`docs/OVERTURE_ENTITY_REVIEW_2026-08-30.md`).
  A second city needs its **own** scoped entity review, not a copy-paste.
  ```bash
  cd backend
  python scripts/run_overture_canary.py --city-slug <new-city> --limit 10
  python scripts/run_overture_canary.py --city-slug <new-city> --limit 10 \
    --stage --batch-id <id> --confirm STAGE_OVERTURE
  # if a staged batch needs to be pulled while still unresolved:
  python scripts/run_overture_canary.py --rollback-batch <id> --confirm ROLLBACK_OVERTURE
  ```
- Staged rows are always blocked `DiscoveryCandidate` rows, never
  user-visible pre-review. Review every row existing-match/alias/stale/
  genuinely-new, the same way Oakland's was. Watch for the entity-matcher
  bug already found once: a shared brand website across chain locations
  being mistaken for proof of identical physical location.

### 2.6 B1 steps 2/4 — NOT execution-ready, scope first
- Real image fetch + hand-labeling. Unlike 2.1/2.2/2.5, this has no exact
  cohort, command, acceptance criteria, or rollback plan yet. Do a short
  scoping pass first (pick a cohort per §3 below, name the exact
  extraction method, define stop/rollback conditions), write it up as its
  own addition to `.agent-bridge/claude-to-codex.md`, *then* claim it.

## 3. Beyond the six items: avenues not yet attempted at all

Everything above works within sources already wired into the codebase.
These are real, listed-but-untried free sources from `docs/
POPULATION_READINESS.md`'s own "Free-source order" — building an adapter
for one of these is legitimate work **even without production access**
(it's sandboxed extractor/adapter code + tests, the same shape as Track 2
Phase C), so a repo-only Claude session can pick these up too, then hand
the resulting tested code to a production-access session for the actual
canary:

- **Municipal health/license/permit datasets.** Authoritative local
  existence/address evidence, one provider adapter per jurisdiction (same
  shape as the existing Overture/OSM adapters). Nothing built yet for any
  jurisdiction — this is new adapter code, not a config flip.
- **AllThePlaces published weekly output.** First-party locator URLs and
  chain-location gaps Overture may miss. Consume the published data
  directly — do not rerun the spider fleet yourself. No adapter exists yet.
- **Foursquare Open Source Places.** Only after measuring which gaps
  Overture's own upstream Foursquare/Meta contributions don't already
  cover — a blind union would just duplicate existing candidates. Needs a
  gap-measurement pass before any adapter work, since Overture may already
  contain this data.
- **OSM regional/bounding-box acquisition.** Independent corroboration and
  gap-filling beyond Overture, via Nominatim/Overpass — must stay
  low-rate, identified, cached, and incremental, never an unbounded dump.

None of these are claimed by anyone as of this writing. Building a sandboxed
adapter + fixture-based tests for any one of them (following the same
pattern as `backend/app/services/discovery/overture_places.py`) is real,
valuable, production-access-independent work — it just doesn't move a
coverage number until a production-access session runs the resulting
canary.

## 4. What "done" looks like for this whole workstream

Per `docs/CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`'s own
completion definition, still true here:

- At least one free menu cohort and one free photo cohort have honest
  precision/recall evidence (not just an attempt — an actual measured
  outcome, even a negative one).
- Production writes stay exact-ID, bounded, attributable, reviewed, and
  reversible or quarantined.
- Coverage movement is measured with reproducible before/after queries on
  the same denominator.
- Recurring acquisition remains disabled unless it separately passes an
  independent production-safety review.

If a source yields no safe gain, document why and move to the next source
shape — do not widen a failing method to manufacture a higher percentage.

## 5. Where to record results

- A dated evidence doc (`docs/POPULATION_<CANARY>_<DATE>.md`, matching the
  existing `OVERTURE_ENTITY_REVIEW_2026-08-30.md`/`POPULATION_RELEASE_PASS_
  2026-09-01.md` naming pattern) for the actual before/after counts and
  per-row review notes.
- `.agent-bridge/STATE.md` and `.agent-bridge/claude-to-codex.md`, per
  `PROTOCOL.md`'s handoff contract — commit SHA, exact checks run,
  remaining gaps, one concrete next action.
- `CRAVE_STATUS.md`'s population-baseline table, once a canary's counts are
  confirmed and stable, so the next session doesn't work from stale
  numbers the way this document had to.
