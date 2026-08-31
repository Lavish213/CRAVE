# H-20260830-data-readiness-reviewed
Status: information-only
Owner: Claude
Branch: main
Base SHA: 8676c7bbed7e248d1cabad1fb24ca35950e57e60
Commit SHA: 8676c7b
Allowed next files: none — this is a review handoff, not a code change

## Outcome
Codex, this is addressed to you directly: your `codex-to-claude.md` handoff
above (H-20260830-data-readiness-pass) was found and reviewed while your
session was offline -- the user asked me to pick it up rather than let it
sit. PR #68 is merged. Full review with all specifics is on the PR #68
GitHub thread; summary here.

The scheduler investigation is genuinely good, careful work -- checking it
at process/service/log/workflow/database layers before concluding, rather
than trusting one log line, is exactly right. It also corrects something I
told the user earlier in this session (that "no scheduler running" was the
most urgent finding) -- it wasn't broken, just running in a separate
Railway project I didn't know about. No further action needed on that
question; don't revisit it.

## Verification
- Reran your new tests myself: `test_menu_source_success_semantics.py
  test_placeholder_menu_cleanup_script.py` -> 4 passed (exact match).
- Full backend suite -> 890 passed, 2 skipped (you reported 889/3 --
  same environment-dependent skip-count drift seen all session, not a
  real discrepancy).
- Traced `record_materialized_source_success()`: confirmed
  `result.materialized` is set once, uniformly, after
  `materialize_menu_truth()`, regardless of which of the four extraction
  paths (provider/hydration/html/advanced-escalation) fed it -- so
  consolidating the four scattered `record_success()` calls into one
  gated call didn't silently drop any legitimate success recording.
- Confirmed `deactivate_placeholder_menu_items.py` imports
  `is_obvious_placeholder_item()` from `menu_publisher.py` rather than
  reimplementing the predicate -- no drift risk.

## Known gaps / risks
- Same as your own handoff: the three placeholder rows are still active
  (preview/simulate only, no apply run). Live classifier inference still
  unproven (zero PlaceVideo rows). Historical Square/Toast
  `last_success_at` values remain misleading for past runs. Menu
  enrichment throughput/yield still needs profiling before scaling.
- I have no Railway/production access in this session -- the raw
  production counts in your audit rest on your reporting, not my
  independent reproduction. Same limitation as every prior review this
  session.

## Next action
Per your own PR #68 "Remaining controlled actions," in order:
1. Independently re-review the three printed placeholder menu IDs
   yourself before running the exact apply -- merging the tooling isn't
   the same as authorizing the apply.
2. Profile and bound menu-enrichment strategies by domain/time/yield
   before raising batch size or concurrency.
3. Design the bounded byte-based image holdout experiment; do not rerun
   the positional heuristic expecting new semantic information.
4. Investigate why the two historical Square/Toast sources failed
   canonical publication before retrying them.
No scheduler runtime/config change is authorized or needed.
