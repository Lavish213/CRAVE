# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: 141fe8b9a5992d18f5eb00bc2dc8744b0c127b17
Scope: Caught up on all six open Codex PRs (#52-#57) after a session gap.
Merged #52 (iOS UIBackgroundModes fix) and #57 (Map truth/clustering, after
independently rerunning its backend suite). Filed blocking findings on #53,
#55, and #56 as PR comments (GitHub blocks a formal review on this account's
own PRs). #54 still needs independent diff-level verification once #53's
fix lands.
Locked files: none currently held.
Verification plan: n/a — reviewing others' work, not authoring a change.
Next action: Codex fixes the confirmed bugs: PR #53's `price=` constructor
bug (jsonld_menu_extractor.py:157/197, pattern_detectors.py five detect_*
functions), PR #55's 100-vs-200 candidate cap
(backend/app/api/v1/routes/places.py's has_location/no-city branches), and
PR #56's menu-item-image MenuImageBridge bypass in menu_publisher.py — each
with a regression test that actually exercises the previously-broken path.
Claude will re-review #53 once fixed, then #54 (stacked on #53's branch).

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
