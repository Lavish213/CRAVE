# GitHub comments + AI assistant

CRAVE includes an opt-in GitHub Actions assistant for repository collaborators. It answers explicit commands without executing contributed code or changing the repository beyond posting its reply.

## Enable it

1. Review `.github/ai-assistant.md` and `.github/ai-assistant.json` on the default branch.
2. In **Settings → Secrets and variables → Actions**, add the `OPENAI_API_KEY` secret from the OpenAI project approved for this repository.
3. In the same screen, add the repository variable `AI_COMMENTS_ENABLED` with the exact value `true`.
4. If the repository is private, separately add `PRIVATE_CODE_AI_ENABLED` with the exact value `true`. This explicitly authorizes bounded issue and pull-request context to leave GitHub for the configured OpenAI API project.
5. Merge the workflow to the default branch. It cannot run from this feature branch.
6. Open a test issue as a collaborator and comment `/help`, then `/ask What is this issue asking us to change?`.

Without the activation variable—and the private-code variable where applicable—the job is skipped. `/help` is local and makes no OpenAI request. There is no reliable persistent monthly budget mechanism inside GitHub Actions, so configure project-level usage limits and alerts in the OpenAI account as well as the per-request caps in `.github/ai-assistant.json`.

## Commands

- `/ask <question>`
- `/review [optional focus]` on pull requests only
- `/summarize`
- `/help`

Commands must begin the comment. Owners, members, collaborators, and explicitly allowlisted usernames are accepted. Bots and arbitrary public users are rejected before a paid model call.

## Security model

- The workflow checks out the default branch, never the pull-request head.
- Pull-request files and patches are read as untrusted text through GitHub's API and never executed.
- Workflow permissions are limited to reading contents and writing comments.
- Common credential formats are redacted before context is sent.
- Context, comment count, diff size, output, retries, and runtime are bounded.
- A source-comment marker and concurrency key prevent duplicate paid replies.
- Errors are generic and do not expose response bodies, tokens, or prompts.
- The assistant cannot approve, merge, push, label, or edit files.

Review the configured OpenAI project's current data controls before enabling private-code access. Secret redaction is defense in depth, not proof that proprietary context contains no sensitive information.

## Local verification

```bash
npm ci --ignore-scripts
npm test
npm run build
```

Tests cover parsing, authorization, bot rejection, allowlists, redaction, prompt-injection boundaries, context limits, deduplication, API scoping, transient failures, and safe errors.
