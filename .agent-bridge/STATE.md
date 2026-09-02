# Active agent state

Status: ready-for-review
Owner: Claude
Branch: claude/project-grade-systems-review-4ot7d0 (PR #123 open against
main, branch restarted from main since the old branch of this name
carried no unique commits)
Base SHA: bf0b08c367250b696d54817dcaeca44fd165e1ea
Commit SHA: 720f59e6b2d39e9260db10c8a70f1d8fe3d6fdd6
Scope: Two independent, code-only Product-lane passes (no Railway/
Supabase access used) -- finished the two hostable legal docs
(privacy-policy.md, terms-of-service.md), the Expo SDK 54->55 upgrade,
and (this update) the two pre-existing CI regressions PR #123 inherited
from `main` -- root/backend requirements.txt drift and the Node 20 vs.
Node 22 Supabase-realtime WebSocket incompatibility, same root causes
Codex independently found and fixed in PR #124. Full detail in
`.agent-bridge/claude-to-codex.md`.

Locked files: none -- handoff complete, no further work planned on this
branch pending review.

Verification: `tsc --noEmit` clean; frontend Jest 331/331 (34 suites);
`npx expo config --type public` resolves sdkVersion 55.0.0 cleanly;
local requirements.txt drift-check script passes; CI status pending
re-run against this update (previously failed on the two now-fixed
issues above -- see PR #123's check runs for current state).

Known gaps: PR #123's Expo 55 upgrade is still unverified at the
native/device level (no EAS build/prebuild anywhere, Linux container
here has no Xcode/simulator). Neither legal doc has a hosted URL yet.
Both PR #123 and PR #124 are green (or expected green) at the code/CI
level but still need a human's required approving review before either
can merge -- branch protection requires it and the PR author can't
self-approve.

Next action: whoever reviews -- merge #124 first (no dependency on
#123, already fully green), then re-verify #123's CI now that it
carries the same requirements.txt/Node-22 fixes independently (it does
not depend on #124 merging first, both fixes were applied directly to
#123's branch too to avoid a merge-order dependency).
