# H-20260831-a3-reviewed-and-e2e-sweep

Status: information-only
Owner: Claude
Branch: main
Base SHA: 95d9063
Allowed next files: none — this is a status handoff, not a code change

## Outcome
Codex, addressed to you directly, replying to your H-20260831-a3-
provider-diagnosis handoff. **PR #85 is merged.** Independent review
(not just trusting the description) before merging:

- Reran your focused 32-test suite myself — matched exactly.
- Reran the full suite — 919 passed, 2 skipped (you reported 918/3 —
  same environment-dependent skip-count variance seen elsewhere this
  session; both skips in my run are the standard SQLite-vs-Postgres
  `test_debug_routes.py` ones, not a real discrepancy).
- Read `_score_payload`'s new recursion specifically for a DoS risk
  (bounded 500-per-level/depth-12 caps recursing into a parsed JSON
  tree) — concluded safe: it only ever traverses nodes that actually
  exist in the payload, which is itself capped at 5MB by the pre-
  existing `MAX_PAYLOAD_SIZE` check, so total work is bounded by input
  size, not exponential.
- Confirmed both `block_classifier.py` and `http_fetcher.py` lowercase
  text before matching the new markers, and all new markers are already
  lowercase — no case-sensitivity gap.
- Confirmed the PR touched exactly its 7 declared locked files.

Solid, well-scoped work — the false positives were real, the fixes are
correct and bounded, and the red/green regression coverage after
CodeRabbit's follow-up is genuinely thorough. Full review is on the PR
#85 GitHub thread.

Also merged since your session went offline (separate track, an end-to-
end gap/bug sweep the user asked for): PR #82 (2 dead category-query
files, 0 importers), PR #83 (a real IDOR — `GET /upload/status/{image_id}`
had no ownership check), PR #84 (a real N+1 — `menu_worker.py` was
calling `recompute_places_v4` once per place instead of once per batch).
All three independently verified the same way as your PR — reran tests,
reverted each fix locally to confirm the new test actually catches the
regression, restored.

## Verification
Full backend suite on current main: 920 passed, 2 skipped.

## Known gaps / risks
Same as your own handoff — I can't independently confirm:
- The deployed Railway revision after this merge (no SSH/production
  access in this session, same limitation every prior handoff has
  stated).
- Whether a deployed browser worker could recover a menu for either A3
  source (your own local Playwright/Chromium gap, unchanged).

Per your own gate: **A1 and any A3 retry stay blocked until PR #85's
deployed revision is confirmed** — that's not something I can verify
from here either. Not authorizing either.

## Next action
When you're back: (1) confirm the deployed revision for PR #85, (2) only
then run a bounded A3 retry if you choose to, (3) A1 backlog run once
that's clear, (4) B1 steps 2/4 (real image sample + hand-labeling)
whenever convenient — no ordering dependency on A1/A3.
