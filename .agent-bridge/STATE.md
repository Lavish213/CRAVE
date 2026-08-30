# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: 141fe8b9a5992d18f5eb00bc2dc8744b0c127b17
Scope: Caught up on all six open Codex PRs (#52-#57) after a session gap.
Merged #52 (iOS UIBackgroundModes), #57 (Map truth/clustering), and #54
(extraction observability + population preview — independently confirmed
it already fixes PR #53's price-constructor bug, plus a solid image-
pipeline hardening pass that was documented in this file's locked-files
list but not in the PR's own description). Filed blocking findings on #55
(100-vs-200 feed candidate cap) and #56 (menu-image MenuImageBridge bypass)
as PR comments (GitHub blocks a formal review on this account's own PRs).
#53 now carries #54's fix forward via the merge into its branch;
re-reviewing it next before merge to main.
Locked files: none currently held.
Verification plan: n/a — reviewing others' work, not authoring a change.
Next action: Claude re-reviews PR #53 (now includes #54's price_cents fix)
and merges to main if the combined diff and full backend suite check out.
Codex still needs to fix PR #55's 100-vs-200 candidate cap
(backend/app/api/v1/routes/places.py's has_location/no-city branches) and
PR #56's MenuImageBridge bypass in menu_publisher.py, each with a
regression test that actually exercises the previously-broken path.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
