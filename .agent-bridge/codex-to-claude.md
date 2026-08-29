# H-20260829-extraction-heuristics
Status: ready-for-review
Owner: Codex
Branch: codex/extraction-heuristics-pass
Base SHA: f8a7f751d9837314ab02eeed326348db7d32249e
Commit SHA: 7ea044e
Allowed next files: none until review

## Outcome
Audited the active menu extraction path end to end and repaired contract drift
that disabled provider normalization, erased price/image snapshot evidence,
made price-aware ranking ineffective, collapsed distinct price variants, and
crashed seven integer-price dedupe paths. Added a cheap structural quality gate
so high-count navigation scrapes cannot bypass the deterministic fallback
ladder. No paid service or new runtime dependency was added.

## Verification
- `/Users/angelowashington/CRAVE/venv/bin/python -m pytest tests/test_menu_extraction_heuristics.py -q` → `12 passed`
- extraction/menu/provider/snapshot test selection → `108 passed`
- `/Users/angelowashington/CRAVE/venv/bin/python -m pytest -q` → `829 passed, 3 skipped`
- `git diff --cached --check` before commit → passed

## Known gaps / risks
- This pass improves deterministic selection and contract correctness; it does
  not add a persisted endpoint-recipe cache, historical drift scoring, or a
  live-domain fixture corpus. Those should be separate measured changes.
- The shared local virtualenv was missing four already-declared packages
  (`pdfminer.six`, `playwright`, `pyarrow`, `h2`); they were installed locally
  solely to run the repository-required suite. No dependency file changed.

## Next action
Inspect commit `7ea044e`, independently run the targeted and full backend tests,
and review the quality thresholds before approving the PR.
