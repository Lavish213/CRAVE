# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: b90b97c (PR #77 merged)
Scope: Continuing through CRAVE_MASTER_PLAN_2026-08-31.md items that don't
need production/device access, per the user's "if ya cant do it leave for
codex do what u can do keep going" instruction, since Codex's session is
still offline.

Done this pass (since the last STATE.md update, which only covered
through PR #75):
- E9: PR #77 merged. Added a bounded, dependency-free fuzzy fallback
  (stdlib difflib.SequenceMatcher, no Postgres extension) to
  search_query.py's search_places() -- fires only when the exact-match
  path returns zero results. 4 new tests.
- B1: PR #78 open (self-reviewed, awaiting CI before merge). Design doc
  at docs/IMAGE_CLASSIFICATION_HOLDOUT_DESIGN_2026-08-31.md -- key finding
  is that the "already-bundled TFLite classifier" your earlier audit
  gestured at is app/services/video/food_classifier.py (real MobileNetV2
  model), not image_classifier.py (the URL-heuristic responsible for the
  77,701 unknown images). Added score_image() wrapper + 2 tests. Steps 2
  (real image fetch) and 4 (manual holdout labeling) are explicitly
  blocked in this session -- no production image URLs, no image-viewing
  capability against fetched content here.

Partial / needs your production access (unchanged from before):
- A3 (the 2 historical Square/Toast sources): ruled out the
  MIN_VALID_ITEMS/MIN_ITEMS_TO_EMIT mismatch hypothesis via static
  tracing. Needs your query access to see what Itani Ramen's (Toast) and
  Reem's California's (Square) actual PlaceClaim/PlaceTruth rows contained.
- A1 (run the 13,148-place menu backlog with the new throughput budgets
  from PR #74) -- needs production access to run.
- A7 (new source discovery beyond BentoBox) -- same.
- B1 steps 2 and 4 above.

Locked files: none currently held.
Verification plan: full backend suite green on each change (908 passed,
2 skipped as of PR #78's branch); every new/changed test independently
verified to catch its corresponding regression (temporarily reverted,
watched fail, restored) before merge.
Next action: Codex, when back: (1) merge PR #78 if CI is green and I
haven't already, (2) A1 backlog run now that throughput is bounded (PR
#74) and BentoBox coverage exists (PR #75), (3) A3 with actual production
row data, (4) B1 steps 2/4 (real image sample + manual labeling) once
A1/A3 are handled.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
