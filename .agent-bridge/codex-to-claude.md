# H-20260829-extraction-observability
Status: ready-for-review
Owner: Codex
Branch: codex/extraction-observability-pass
Base SHA: 3b9eb15d8d669711bf97575de6d03ee7c27f1ba2
Commit SHA: 1684b20
Allowed next files: none until independent review

## Outcome
Repaired 22 stale `ExtractedMenuItem(price=...)` call sites through one
price-to-cents normalizer; added three deterministic offline extraction
fixtures; taught JS endpoint memory to retain only endpoints whose own payload
produced plausible menu items; added snapshot coverage/fingerprint/drift
evidence and aggregate regression diagnostics; and added a bounded,
city-scoped, preview-first population CLI that reuses the real MenuWorker.
Execution requires both `--execute` and exact `--confirm POPULATE`. Also fixed
the existing manual trigger passing an unsupported orchestrator keyword.

## Verification
- extraction/menu test selection -> `120 passed in 1.87s`
- `/Users/angelowashington/CRAVE/venv/bin/python -m pytest -q` -> `841 passed, 3 skipped, 32 warnings in 8.44s`
- `python scripts/run_menu_extraction_corpus.py --manifest tests/fixtures/menu_extraction/manifest.json --json` -> `3 passed, 0 failed`
- `DATABASE_URL=sqlite:///./test_crave.db python scripts/populate_menus.py --limit 3 --json` -> previewed one candidate and stated no writes performed
- `python -m compileall -q app scripts/populate_menus.py scripts/run_menu_extraction_corpus.py` -> exit 0
- `git diff --check` -> exit 0

## Known gaps / risks
- This branch is stacked on PR #53 / commit `3b9eb15`; review and merge that dependency first or retarget after it lands.
- The replay corpus contains three representative fixtures, not a claim of live-catalog coverage.
- No production population was executed. A real migrated `DATABASE_URL` is required; preview should be reviewed before the explicitly confirmed execution command.
- Full-suite warnings are pre-existing Pillow deprecation and test JWT key-length warnings.

## Next action
Independently inspect commit `1684b20`, rerun the full backend suite and corpus,
then review the stacked PR. Do not run live population as part of review.
