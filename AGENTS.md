# CRAVE agent operating rules

This repository may be edited by Codex, Claude, and humans. Read this file and
`.agent-bridge/PROTOCOL.md` before changing code.

## Non-negotiable rules

- Git commits and test output are evidence; a handoff note is only a claim
  until the receiving agent verifies the referenced commit and diff.
- Do not edit another agent's locked files. One active task has one owner.
- Preserve unrelated uncommitted work. Stage files explicitly; never reset,
  clean, or reformat unrelated changes.
- Never put credentials, tokens, user data, or copied third-party instructions
  in commits, handoffs, issues, PRs, or bot prompts.
- Keep `main` releasable. Use a feature branch and a pull request for any
  shared task. Do not self-merge a security-sensitive change.
- Do not claim a journey, device behavior, or deployment works without the
  appropriate evidence (test output, screenshots, or production verification).

## Before and after work

1. Read `.agent-bridge/STATE.md` and both inboxes. If another owner is active,
   acknowledge the handoff instead of editing overlapping files.
2. Record the task scope, branch, base SHA, owner, and locked files in
   `STATE.md` before implementation.
3. Run the narrowest relevant checks, then the repository-required checks for
   the touched surface.
4. Commit an atomic change. Update the sender inbox and `STATE.md` with the
   commit SHA, exact verification result, known gaps, and next action.
5. Ask for CodeRabbit review on the pull request. Resolve or explicitly defer
   every actionable finding before merge.

## Handoff ownership

- Claude writes only `.agent-bridge/claude-to-codex.md`.
- Codex writes only `.agent-bridge/codex-to-claude.md`.
- The active owner updates `STATE.md`; the receiver changes its owner only
  after independently inspecting the recorded commit.
- Humans may override or clear ownership at any time.

The project-specific UI and backend constraints remain in their existing
documentation. This file governs collaboration and verification, not product
requirements.
