# Collaboration decisions

## ADR-001 — Git is the handoff transport

Git commits, pull requests, and the bridge files carry durable context. They
do not wake another agent; a human or configured automation still starts the
receiver.

## ADR-002 — One active owner and explicit file locks

Serial handoffs are the default for overlapping code. Parallel work requires
separate branches/worktrees and non-overlapping file ownership.

## ADR-003 — Verification evidence outranks prose

Commit SHAs, diffs, CI logs, tests, screenshots, and production evidence are
authoritative. Handoff notes summarize them but cannot replace them.

## ADR-004 — Review bots are advisers, not merge authorities

CodeRabbit checks pull requests after installation. CI, CodeQL, a human or
receiving-agent review, and branch protection remain the release gate.
