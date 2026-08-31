# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: 8676c7bbed7e248d1cabad1fb24ca35950e57e60
Scope: Independently reviewed and merged PR #68 (data-readiness pass) while
Codex's session was offline. Reran the new focused tests (4 passed) and the
full backend suite (890 passed, 2 skipped) myself in a clean worktree,
traced record_materialized_source_success() to confirm it's wired
correctly for all four extraction paths (provider/hydration/html/
escalation) via the single result.materialized checkpoint, and confirmed
the placeholder-cleanup script reuses is_obvious_placeholder_item() rather
than reimplementing it. Full review is on the PR #68 thread for Codex to
read when it's back, including an explicit note that the scheduler finding
corrects earlier advice I gave the user (I'd said "no scheduler" was the
headline problem; Codex's multi-layer check found it's running fine in a
separate Railway project, `rare-sparkle` — good catch, don't revisit it).
Locked files: none currently held.
Verification plan: n/a — review complete.
Next action: Codex, when back: per your own PR #68 "Remaining controlled
actions" — (1) independently re-review the three printed placeholder menu
IDs yourself before running the exact apply (don't skip this just because
I merged the tooling; the apply itself is a separate, still-gated act),
(2) profile/bound menu-enrichment throughput per-domain before raising
batch size or concurrency, (3) design the bounded byte-based image holdout
experiment rather than rerunning the positional heuristic, (4) investigate
why the two historical Square/Toast sources failed canonical publication
before retrying them. No scheduler config change is authorized or needed.

Item 0 is DONE (PR #71, merged as `876dbc0`) — I implemented and locked it
myself per the human's explicit request rather than waiting for Codex.
`allow_llm_fallback` and `allow_browser_escalation` are now independent
parameters on `extract_menu()`/`_run_extraction_pass()`;
`menu_orchestrator.py` passes `allow_llm_fallback=False` explicitly.
Also fixed a hardcoded `allow_llm_fallback=True` on the post-browser-
escalation retry path that would have silently re-enabled the LLM on
retry regardless of the caller's setting -- that one would have been
easy to miss. Three tests lock this: two direct-call tests plus an
AST-based static guard on `menu_orchestrator.py`'s call site (same
pattern as the existing price-contract guard), so it survives future
refactors. All three were verified to actually fail without their
corresponding fix (temporarily reverted each, watched it fail, restored),
not just written to pass. Full suite: 893 passed, 2 skipped.
`replay_corpus.py` updated too, since splitting the flags changed its
previously-coupled fully-offline behavior.

Codex: menu extraction is now genuinely free-route-only in code, not
just by convention. Safe to proceed with the throughput/batch-size
profiling work from the prior note.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
