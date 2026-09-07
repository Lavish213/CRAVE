# H-20260907-population-coverage-canaries

Status: information-only
Owner: Claude (handoff) -> Codex (execution)
Branch: none from me -- this is a task handoff, not a diff
Base SHA: b213f55fd431dbf1670214795352021ba5e8b66e (main, current as of this
handoff)
Commit SHA: none
Allowed next files: none from me on this topic

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

### 6. B1 steps 2/4 -- real image fetch + hand-labeling
- Untouched since the brief was written. Needs production access to even
  start; no local/sandbox proxy exists for this one. No further detail
  to add beyond `CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`
  Phase C/Phase E's classification-vs-acquisition distinction --
  `run_phase3_image_backfill.py` is classification only, not a source of
  new images.

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
Pick one item at a time, each as its own PR per
`CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md`'s "Required
deliverables" list (baseline evidence, extractor fix, canary evidence,
image promotion, and any scheduler expansion all stay in separate PRs).
Item 1 (menu backlog canary) or item 5 (second-city Overture) are the
most concretely actionable next steps; items 3/4 are blocked on either a
real stuck-image/real-device scenario occurring or being deliberately
staged, and item 6 needs its own scoping pass first.

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
