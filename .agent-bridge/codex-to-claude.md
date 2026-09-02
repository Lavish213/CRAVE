# H-20260901-population-release-revalidated

Status: ready-for-review
Owner: Codex
Branch: codex/population-release-pass
Base SHA: bf0b08c
Commit SHA: 7b14ce9 (latest implementation commit; review full `bf0b08c..HEAD`)
Allowed next files: review/comments only; do not run production jobs from this handoff

## Outcome

The branch was not based on current `main`: its old merge base was `685c57c`.
I rebased it onto `bf0b08c`, preserving PRs #117/#118/#121/#122 and dropping
the obsolete pre-rebase claim/handoff plus the stale frontend dependency
downgrade.

I reran both requested exact-target production canaries after the rebase:

- Menu: the same three reviewed places produced attempted=3,
  materialized=0, no_menu=3, errors=0. Itani's formerly contaminated result
  now logged `menu_pipeline_rejected reason=low_quality`, so the new gates
  prevented republication. Pizzaiolo still hit a CAPTCHA. Coverage gain: zero.
- Free images: the first post-rebase retry was invalidated by the canary's own
  24-hour fetch cache. After adding a regression-tested canary-only bypass, the
  corrected exact retry produced attempted=2, staged=1,
  publicly_visible=0. Cantina yielded one hidden/non-primary image; Las Ranas
  yielded none. Google was structurally unreachable.

The rebased R2 signed-HTTP fix initially broke PR #122's local R2 test double;
I updated that boundary to exercise the signed-HTTP stream. Both real
ffmpeg/classifier upload-pipeline tests pass again. No production video was
retried and no recurring job was enabled.

PR #124's first CI run exposed an unrelated but release-blocking drift already
present on `main`: eight dependency floors had been updated only in
`backend/requirements.txt`, while Railway installs root `requirements.txt`.
Commit `7b14ce9` synchronizes exactly those eight lines; it adds no dependency.
That rerun then exposed a second base-branch CI mismatch: the upgraded Supabase
realtime client expects Node 22's native WebSocket during Jest startup, while
CI still pinned Node 20. The frontend CI runner now uses Node 22, matching the
supported local runtime; no app or frontend dependency changed.

## Verification

- `git merge-base --is-ancestor origin/main HEAD` before rebase -> exit 1;
  old merge base `685c57c`.
- `git rebase origin/main` -> completed; branch now starts at `bf0b08c`.
- `/Users/angelowashington/CRAVE/venv/bin/python -m pytest -q backend/tests/test_menu_backlog_canary_script.py backend/tests/test_free_image_canary_script.py backend/tests/test_r2_client.py backend/tests/test_streak_service.py backend/tests/test_menu_entity_match.py backend/tests/test_website_image_extractor.py backend/tests/test_menu_pipeline_quality_gate.py` -> 44 passed.
- `/Users/angelowashington/CRAVE/venv/bin/python -m pytest -q backend/tests/test_r2_client.py backend/tests/test_video_upload_pipeline_end_to_end.py` -> 7 passed.
- `/Users/angelowashington/CRAVE/venv/bin/python -m pytest -q backend/tests` -> 1025 passed, 2 skipped.
- Production menu preview -> found=3, missing=0, inactive=0.
- Production menu run with exact `--confirm-count 3` -> attempted=3,
  materialized=0, no_menu=3, errors=0.
- Production image preview -> found=2, existing image blockers=0.
- Corrected production image run with exact `--confirm-count 2` -> attempted=2,
  staged=1, publicly_visible=0.
- Post-canary production audit -> all three menu targets `has_menu=false`,
  active menu items=0; one exact image row, hidden/non-primary; scheduler
  allowlist unchanged at the four reviewed free/local jobs.
- `git diff --check` -> clean.
- Root/backend package-line comparison -> exact match; backend `compileall`
  and `import app.main` -> clean.
- Clean `npm ci` on Node 22, then `npx tsc --noEmit && npx jest --ci` ->
  typecheck clean; 34 suites, 331 tests passed.

## Known gaps / risks

- The menu quality fix is demonstrated as a safety improvement, not a recall
  improvement. Recurring menu enrichment should remain disabled.
- Cantina's official site says temporarily closed/reopening; do not promote its
  staged image without entity-status review. Las Ranas currently redirects to
  an image-less lander, so its stored website needs freshness review.
- The R2 production recursion fix is code/test verified only; it still needs
  independent review, deployment, and a one-object quarantined retry.
- Exact production IDs remain in the dated evidence doc. Do not publish/push
  this branch unless the human explicitly approves that repository disclosure.

## Next action

Review `bf0b08c..HEAD`, especially the R2 signed-HTTP change and the updated
PR #122 test boundary. Do not call either acquisition pipeline "coverage
verified": menu recall stayed 0/3 and the one image candidate remains hidden.
