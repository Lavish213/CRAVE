# H-20260830-data-readiness-pass
Status: ready-for-review
Owner: Codex
Branch: codex/autonomous-remainder-pass
Base SHA: ba261a5f
Commit SHA: 473d4f6 plus pending documentation correction
Allowed next files: none

## Outcome
Completed the production data-readiness audit and fixed two confirmed
operational defects: the menu coverage report's ~13k-query N+1, and menu-source
success being recorded before canonical publication. Added a simulation-first,
exact-confirmation cleanup command for three obvious legacy placeholder rows.
No production apply was performed.

The scheduler existence question is now resolved: the API web service
intentionally disables its embedded scheduler, while a separate running
Railway project (`rare-sparkle`) owns all 10 scheduled jobs through
`python -m app.scheduler_worker`. Current worker logs and production `JobRun`
rows agree. Do not enable the embedded scheduler. The next operational target
is menu-enrichment throughput/yield, not scheduler restoration.

## Verification
- `env PYTHONPATH=/private/tmp/crave-autonomous-remainder/backend /Users/angelowashington/CRAVE/venv/bin/pytest -q` → 889 passed, 3 skipped
- focused menu tests → 26 passed; new focused tests → 4 passed
- optimized Oakland production report → completed; 5,921 active, 216 with menus, 5,384 menu-less with no source, 293 stuck
- production cleanup preview → exactly three rows
- production cleanup simulation with exact sentinel → exactly three rows, transaction rolled back
- consolidated read-only SQL audit → catalog/image/event counts recorded in dated report
- `git diff --check` → passed

## Known gaps / risks
- Live classifier inference remains unproven because production has no videos.
- Existing historical Square/Toast `last_success_at` values remain misleading;
  this change corrects future writes but does not rewrite history.
- Placeholder rows are still active until a separately reviewed exact apply.
- Image semantic coverage cannot improve by rerunning the positional heuristic.
- Menu enrichment is scheduled but one observed run exceeded 17 minutes and
  spent substantial time on low-yield generic endpoint/API probes. This needs
  profiling and bounding before batch/concurrency increases.

## Next action
Review PR #68 and independently rerun tests. If merged, separately review the
three printed IDs before authorizing the exact production cleanup apply. Also
verify the documented separate-worker evidence and treat menu throughput as the
next investigation; no scheduler runtime/config change is proposed.
