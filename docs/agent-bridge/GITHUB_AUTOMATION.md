# GitHub AI collaboration and review setup

## What is now in the repository

- `.agent-bridge/` is the durable Codex ↔ Claude handoff protocol.
- `AGENTS.md` and `CLAUDE.md` make the protocol discoverable to coding agents
  and CodeRabbit.
- `.coderabbit.yaml` configures focused automated PR review.
- `.github/PULL_REQUEST_TEMPLATE.md` requires test evidence, known gaps, and
  handoff metadata.
- `.github/workflows/ask-crave.yml` is an opt-in comment responder. It replies
  only when an owner, member, or collaborator writes `/ask-crave <question>`
  on an issue or PR.

This is asynchronous collaboration through Git. It does not let ChatGPT log
into Claude, let Claude control Codex, or create a hidden conversation between
agents. A new commit/handoff still needs a human or automation to start the
other agent.

## One-time maintainer setup

1. Install and authorize the CodeRabbit GitHub App for `Lavish213/CRAVE`.
2. In GitHub repository settings, add branch protection for `main`: require
   the CI and CodeQL checks, require a human review, and block force pushes.
3. Create a dedicated OpenAI API project/service-account key with a small
   spend limit. Add it only as GitHub repository secret `OPENAI_API_KEY`.
4. Optionally add repository variable `OPENAI_MODEL`; otherwise the workflow
   uses `gpt-4.1-mini`. Ensure the chosen model is enabled for that API project.
5. Merge this workflow to the default branch. GitHub runs `issue_comment`
   workflows from the default branch, not an unmerged PR branch.
6. Test in a private issue with `/ask-crave What verification is required for
   this change?` Verify that only the bot response appears and that no secret
   appears in logs or comments.

Never put the OpenAI key in frontend code, `.env.example`, a commit, a PR
comment, or a handoff. If it is exposed, revoke/rotate it immediately.

## Operating flow

1. An agent claims a bounded task in `.agent-bridge/STATE.md` and locks files.
2. The agent commits the change and writes a factual handoff with SHA and test
   results.
3. The receiving agent fetches that SHA, independently checks it, and either
   acknowledges it or marks it blocked.
4. Open a pull request. CI, CodeQL, the receiver/human review, and CodeRabbit
   check it. Use `@coderabbitai review` if an automatic review did not run.
5. Merge only after required checks and a human approver agree.

## Boundaries of the comment bot

The bot is intentionally not a code executor, reviewer, or merge authority.
It does not check out repository code, access repository contents, or run
terminal commands. It receives the OpenAI secret only as an Actions secret,
receives events only from members, truncates the invoking question, and can
only write a single comment.

For implementation or code review, use the agent bridge and a PR. For a
question or a concise handoff clarification, use `/ask-crave`.

## Verification before enabling

Run these repository checks on the branch that adds the workflow:

```sh
git diff --check
```

Then inspect the rendered workflow in GitHub. The first live test needs the
maintainer-provided secret; do not replace it with a fake key or bypass the
authorization condition just to make a test pass.
