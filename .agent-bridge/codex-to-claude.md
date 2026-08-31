# H-20260831-a3-provider-diagnosis

Status: ready-for-review
Owner: Codex
Branch: `codex/a3-production-diagnosis`
Base SHA: `8484f14`
Implementation commit: `4891f0e`
Locked files: see `.agent-bridge/STATE.md`

## Scope and outcome

A3 only. I queried the two historical Square/Toast source lineages through
Railway in read-only mode and ran bounded live provider probes. I did not retry
an orchestrator job, write to production, or change either source row.

Both sources have zero `PlaceClaim`, `PlaceTruth`, and `MenuItem` rows. Their
historical `last_success_at` values predate PR #68's corrected success
semantics; there is no failed canonical state to repair.

Confirmed and fixed three extraction false positives:

1. zero-signal generic JSON could be selected as hydration and become a fake
   one-item menu;
2. `block_classifier` treated any mention of Cloudflare as a challenge;
3. `http_fetcher` independently repeated the same broad token check.

Current results after the fixes:

- Itani/Toast: public document retrieved through the existing impersonation
  fallback, 0 raw / 0 valid items.
- Reem's/Square: public page and catalog fetched, 1 event-ticket product, not a
  restaurant menu. The existing two-item gate correctly rejects it.

Full sanitized evidence is in
`docs/A3_PROVIDER_FAILURE_DIAGNOSIS_2026-08-31.md`.

## Verification

- Red/green regression reproduced for zero-signal hydration and the benign
  Square Cloudflare feature flag.
- Focused extraction suite: `27 passed in 0.82s`.
- Full backend suite from `backend/` with `TZ=UTC`:
  `913 passed, 3 skipped, 32 warnings in 6.99s`.
- `git diff --check`: clean before commit.

The `TZ=UTC` setting avoids three known local-date streak-test failures when
Los Angeles and UTC are on different calendar dates; baseline main produced
the same issue without the setting.

## Known gaps and review requests

- No production retry is authorized by this PR. Retry only after review,
  merge, and deployment, and keep it bounded.
- Local Toast Playwright escalation could not launch because its Chromium
  binary is not installed. Do not interpret that as proof a browser worker can
  or cannot recover a menu.
- Please independently inspect the challenge-marker narrowing and confirm that
  real challenge/CAPTCHA/access-denied cases remain covered.
- Ask CodeRabbit to review the PR. Do not merge on this handoff alone.

## Next action

Review commit `4891f0e`. If accepted and deployed, A1 may proceed as a bounded
canary; do not run the full 13,148-place backlog at once.
