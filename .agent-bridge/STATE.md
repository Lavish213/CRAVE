# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/population-release-pass
Base SHA: bf0b08c
Scope: Revalidate the bounded website-menu and free-image acquisition canaries
against current `main` after PRs #117, #118, #121, and #122. Preserve newer
merged work, run exact-target previews before any bounded production attempt,
and refresh the evidence/handoff without claiming results from the old base.

Implementation commits: `9aadfab`, `cff3107`.
Result: current-main menu canary safely produced 0/3 menus; current-main free
image canary safely produced 0/2 image candidates. Full backend suite passes
1024 tests with 2 skips. No recurring acquisition job was enabled.

Locked files:
- `backend/app/services/upload/r2_client.py`
- `backend/scripts/run_free_image_canary.py`
- `backend/tests/test_free_image_canary_script.py`
- `backend/tests/test_r2_client.py`
- `backend/tests/test_streak_service.py`
- `backend/tests/test_video_upload_pipeline_end_to_end.py`
- `docs/POPULATION_RELEASE_PASS_2026-09-01.md`
- `.agent-bridge/codex-to-claude.md`
- `.agent-bridge/STATE.md`

Verification plan:
1. Run focused tests for the retained changes and both canary tools.
2. Run the complete backend suite.
3. Preview exact production targets with paid/unbounded jobs still disabled.
4. Run only canaries whose preview/drift gates remain clean, then inspect their
   staged/non-public outcomes.
5. Record exact commands/results and unresolved production risks for review.

Explicit exclusions:
- No recurring scheduler allowlist expansion.
- No paid Google/provider calls.
- No bulk population or public promotion.
- No frontend dependency changes; current `main` remains authoritative.
- Primary-checkout dirty files remain untouched.
