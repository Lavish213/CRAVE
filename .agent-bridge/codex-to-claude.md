# H-20260830-overture-entity-review
Status: ready-for-review
Owner: Codex
Branch: codex/overture-entity-review
Base SHA: 476ad3a7d85c46e48312a2e6f2265c22a1060782
Commit SHA: 98d1ed7
Allowed next files: review only; do not run the production `--apply` command

## Outcome
Completed the evidence-backed review of all ten production rows in batch
`oakland-20260830-a`. The fixed disposition is 3 existing matches, 1 historical
alias, 5 stale rejects, and 1 verified-new location. Added an exact-ID,
exact-confirmation apply tool and a rollback-only simulation mode. Also fixed a
live entity-matcher defect where a shared brand domain could merge two distant
branches; without that fix, Jackson Street Sandwicheez would merge into Kaiser
Center instead of becoming its own physical location.

## Verification
- `pytest -q tests/test_entity_matcher.py tests/test_overture_entity_review_script.py tests/test_overture_canary_script.py` -> 14 passed.
- Full backend suite -> 886 passed, 2 skipped.
- `python3 -m py_compile ...` and `git diff --check` -> clean.
- Read-only production preview validated all 10 immutable IDs/states -> 3 match,
  1 alias, 5 reject, 1 promote; 3 stale canonical deactivations.
- Full production-connected simulation -> same counts, transaction rolled back.
- Post-simulation read-only proof -> 10 blocked, 0 resolved, 0 promoted,
  Jackson Sandwicheez absent, all 3 stale canonical rows still active.

## Known gaps / risks
- No production disposition has been applied. Batch remains unchanged.
- The reviewed apply will create one public Place and deactivate three stale
  Places, so it requires independent review and merge before execution.
- Generic entity matching still intentionally requires name plus address or
  spatial agreement; shared websites are no longer location proof.

## Next action
Independently inspect commit `98d1ed7`, record/source evidence in
`docs/OVERTURE_ENTITY_REVIEW_2026-08-30.md`, fixed IDs, matcher regression, and
simulation semantics. Approve/merge or request changes. After approval, Codex
can run the exact production apply and verify Feed/Search/Map/Place Detail plus
health and final database counts.
