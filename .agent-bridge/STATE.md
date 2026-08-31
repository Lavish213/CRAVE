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

New item (0, do this first): the human wants menu extraction on the free
route only (no per-request paid providers). Found a real gap while
checking this — `menu_extraction_router.py`'s `extract_menu()` ties
`allow_llm_fallback` and `allow_browser_escalation` to the SAME
`allow_network_fallbacks` flag, and `menu_orchestrator.py` calls it
without overriding either, so it uses the default (`True` for both).
Production menu extraction currently falls through to a paid LLM call
automatically whenever all 7 free strategies miss — there's no way today
to keep Playwright (compute-only) while excluding the LLM (per-request
billed). Split these into two independent parameters, pass
`allow_llm_fallback=False` explicitly from `menu_orchestrator.py`, and
add a test asserting the free-route path never reaches
`_safe_llm_extract` even when every free strategy returns empty. Do this
before any throughput/batch-size scaling work, since scaling a pipeline
that's silently billing an LLM per miss is the wrong order.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
