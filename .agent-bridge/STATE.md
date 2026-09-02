# Active agent state

Status: ready-for-review
Owner: Claude
Branch: claude/project-grade-systems-review-4ot7d0 (PR #123, merging
`main` post-PR#124 to resolve this file's own merge conflict -- both
PRs independently rewrote this section)
Base SHA: c78abed2ffa1b06ff22fe0037ef8ac9156e18e21 (main, post-PR#124 merge)
Commit SHA: a58cb52ac5c0e0ab1bb6df678e4310f851acf64d
Scope: Two independent, code-only Product-lane passes (no Railway/
Supabase access used) -- finished the two hostable legal docs
(privacy-policy.md, terms-of-service.md), the Expo SDK 54->55 upgrade,
and the two pre-existing CI regressions (root/backend requirements.txt
drift, Node 20 vs. Node 22 Supabase-realtime WebSocket incompatibility)
independently found and fixed the same way in both this branch and
Codex's PR #124 (now merged -- see that PR's history for Codex's own
population-release-pass work, which this entry no longer needs to
restate).

Locked files: none -- handoff complete, no further work planned on this
branch pending review/merge.

Verification: `tsc --noEmit` clean; frontend Jest 331/331 (34 suites);
`npx expo config --type public` resolves sdkVersion 55.0.0 cleanly;
full CI green on commit a51d731 (pre-merge) -- all 7 required checks
passed, including the requirements.txt drift check and Node 22 frontend
job.

Known gaps: PR #123's Expo 55 upgrade is still unverified at the
native/device level (no EAS build/prebuild anywhere, Linux container
here has no Xcode/simulator). Neither legal doc has a hosted URL yet.

Next action: merge PR #123 (this branch) into `main` -- it's
independently green and no longer depends on #124's merge order now
that both fixes are carried directly on this branch too.
