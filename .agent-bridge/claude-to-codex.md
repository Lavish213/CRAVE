# H-20260831-b1-design-and-e9-search

Status: information-only
Owner: Claude
Branch: main
Base SHA: b90b97c
Allowed next files: none — this is a status handoff, not a code change

## Outcome
Codex, addressed to you directly, picking up from where H-20260830-data-
readiness-reviewed left off. Since your session went offline the user told
me to keep working through CRAVE_MASTER_PLAN_2026-08-31.md's non-production
items rather than wait. Merged since then:

- **PR #74** (A2 + A6): wall-clock budgets (`MAX_API_PROBE_SECONDS=20`,
  `MAX_IFRAME_PROBE_SECONDS=15`) on the API/iframe endpoint probes in
  `menu_extraction_router.py` -- this is the actual root cause of the
  17-minute production run you flagged: up to 20 API candidates x 8s
  timeout each with only a count cap, no time cap. Also deleted 3 dead
  files (`menu_link_finder.py`, `menu_link_discovery.py`,
  `menu_site_crawler.py`) with zero callers repo-wide.
- **PR #75** (A4): `bentobox_extractor.py` -- narrow adapter for the one
  confirmed-real BentoBox pattern (static PDF on bentoboxcdn.com/
  getbento.com), evidenced by North Beach Sandwicheez in your own entity
  review doc. Registered in `provider_registry.py`.
- **PR #77** (E9): typo-tolerant search fallback in `search_query.py`
  using stdlib `difflib` (deliberately not a Postgres extension --
  unverifiable on Railway's managed instance without your access).
- **PR #78** (B1, design + scaffolding): design doc at
  `docs/IMAGE_CLASSIFICATION_HOLDOUT_DESIGN_2026-08-31.md`. Important
  finding for you specifically: the classifier your data-readiness audit
  called "already-bundled TFLite classifier" without naming is
  `app/services/video/food_classifier.py` -- a real MobileNetV2 model,
  currently only wired to video frames. It is NOT
  `image_classifier.py` (the URL-heuristic behind the 77,701 unknown
  images). Added `score_image()`, a thin wrapper exposing that model for
  single images. This PR does not and cannot execute the actual holdout --
  steps 2 (fetch real image URLs) and 4 (hand-label ~400 images) need
  your production access, not mine.

## Verification
Full backend suite green after every merge (908 passed, 2 skipped as of
PR #78). Every new/changed test in each PR was independently verified to
catch its own regression (temporarily reverted the fix, confirmed the
test failed, restored) before merging -- same discipline as your own
H-20260830 handoff.

## Known gaps / risks
- A3 (Itani Ramen / Reem's California historical Square/Toast failures):
  still blocked on your DB access. I ruled out one hypothesis (the
  MIN_VALID_ITEMS/MIN_ITEMS_TO_EMIT gate mismatch) via static tracing --
  they're numerically aligned, so that's not it.
- A1 (13,148-place backlog run) hasn't been run yet -- now safe to run
  given PR #74's throughput bounding.
- No production/device access in this session for any of the above, same
  limitation as every prior handoff.

## Next action
When you're back, in order: (1) merge PR #78 if I haven't already and CI
is green, (2) run A1's backlog now that throughput is bounded, (3) use
your production access to finish A3, (4) come back to B1 steps 2/4 (real
sample + labeling) once A1/A3 are clear.
