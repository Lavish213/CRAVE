# H-20260827-release-campaign
Status: ready-for-review
Owner: Codex
Branch: codex/release-coordination
Base SHA: 51d51555fd9e8ef3e53e5b724cd29788a1530749
Commit SHA: none
Allowed next files: none

## Outcome
The human explicitly wants us to stop debating ownership and execute one coordinated path to App Store readiness. Proposed split below is risk- and evidence-based, not a permanent frontend/backend monopoly.

### Shared objective
Produce a current-main release candidate that passes protected CI, live Playwright journeys, fresh native Debug/Release builds, a real-device smoke matrix, production-configuration verification, accessibility/performance checks, and App Store operational gates. Do not add product features until a release gate exposes a confirmed blocker.

### Codex track — execution and live verification
1. Configure `main` branch protection through the GitHub API: require the guard, backend SQLite/syntax, backend Postgres/migrations, frontend, and both CodeQL analyses; require resolved conversations and current branches. Preserve the agreed narrow admin-bypass policy only if GitHub can express it safely.
2. Inventory E2E prerequisites by presence only—never print secrets. Run the three Playwright journeys against the approved API/Supabase test configuration when available. Capture exact failures, traces, and screenshots.
3. Generate a fresh Expo/iOS project from current `main`, verify `com.crave.app`, run Debug and Release simulator builds, then execute the documented device smoke matrix.
4. For each reproduced code defect, freeze exact files/acceptance criteria in the bridge before editing and open a dedicated PR. Claude independently reviews cross-cutting or security/production changes.

### Claude track — production and release-readiness audit
1. On a separate branch/worktree, inspect current-main committed configuration for Railway web/scheduler separation, duplicate-job risk, migration/start commands, classifier real-model versus fallback observability, Supabase/JWKS requirements, EAS project/config requirements, push prerequisites, account deletion, privacy/support URLs, and App Store declarations.
2. Classify each item as: verified in code, needs dashboard/human evidence, or confirmed code defect. Do not turn missing external evidence into a speculative code change.
3. Return the smallest ordered human-action checklist with exact dashboard/command evidence required. If a code defect is confirmed, claim only its files and write a frozen acceptance brief before implementing.
4. Review Codex's E2E/native findings and every resulting cross-cutting PR; independently rerun the affected suites before merge.

### Human track
Approve or supply GitHub settings, Apple/EAS/Railway/Supabase account actions, seeded test credentials, physical-device confirmation, App Store metadata, and genuine product decisions. Secrets stay in the relevant platform store, never Git or bridge files.

### Coordination rules
- Separate worktrees and non-overlapping locks.
- Current code, CI, live logs, screenshots, and device evidence outrank old markdown.
- Small same-surface fixes may be handled by the engaged owner; features, auth/security, migrations, production configuration, ranking, and cross-agent handoffs require independent review.
- No agent self-merges a cross-cutting release change.
- Stop and hand off immediately when a required account, secret, paid action, or product decision is the true blocker.

## Verification
- `git fetch origin main` → current baseline `51d5155`
- `git show origin/main:CRAVE_STATUS.md` → canonical order is branch protection, live E2E/device verification, production configuration, then App Store gates
- `git show origin/main:.agent-bridge/STATE.md` → idle, no locks before this claim

## Known gaps / risks
- The local main checkout contains excluded user-owned changes; this coordination work uses an isolated worktree and must not touch them.
- Live E2E requires approved API/Supabase configuration; Save → Craves additionally needs a seeded test account.
- Apple signing, physical-device testing, and some dashboard settings require the human.
- CodeRabbit is unavailable for this OSS repository; Claude/human review remains the independent gate.

## Next action
Claude: review this split now. If correct, acknowledge it in `claude-to-codex.md`, claim the production/readiness audit on a separate branch, and begin with read-only evidence collection. If incorrect, replace it with a concrete corrected split—do not return to abstract role debate.
