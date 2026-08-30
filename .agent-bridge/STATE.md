# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: 141fe8b9a5992d18f5eb00bc2dc8744b0c127b17
Scope: Caught up on all six open Codex PRs (#52-#57) after a session gap.
Merged #52 (iOS UIBackgroundModes fix, superseding this file's prior
ready-for-review entry for that PR). Filed blocking findings on #53 and #55
as PR comments (GitHub blocks a formal review on this account's own PRs).
#54, #56, #57 still need independent diff-level verification.
Locked files: none currently held.
Verification plan: n/a — reviewing others' work, not authoring a change.
Next action: Codex fixes the confirmed `price=` constructor bug in PR #53
(jsonld_menu_extractor.py:157/197, pattern_detectors.py five detect_*
functions) and the 100-vs-200 candidate cap in PR #55
(backend/app/api/v1/routes/places.py's has_location/no-city branches), each
with a regression test that actually exercises the broken path. Claude will
independently review #54 (stacked on #53, blocked until #53 is fixed), #56,
and #57 next.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
