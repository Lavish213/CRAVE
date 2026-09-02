# H-20260901-population-release-revalidated

Status: ready-for-review
Owner: Codex
Branch: codex/population-release-pass
Base SHA: bf0b08c
Commit SHA: cff3107 (on top of 9aadfab)
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
- Free images: Cantina Frida plus the Los Angeles Las Ranas row produced
  attempted=2, staged=0, publicly_visible=0 even with PR #117's browser
  fallback. Coverage gain: zero. Google was structurally unreachable.

The rebased R2 signed-HTTP fix initially broke PR #122's local R2 test double;
I updated that boundary to exercise the signed-HTTP stream. Both real
ffmpeg/classifier upload-pipeline tests pass again. No production video was
retried and no recurring job was enabled.

## Verification

- `git merge-base --is-ancestor origin/main HEAD` before rebase -> exit 1;
  old merge base `685c57c`.
- `git rebase origin/main` -> completed; branch now starts at `bf0b08c`.
- `/Users/angelowashington/CRAVE/venv/bin/python -m pytest -q backend/tests/test_menu_backlog_canary_script.py backend/tests/test_free_image_canary_script.py backend/tests/test_r2_client.py backend/tests/test_streak_service.py backend/tests/test_menu_entity_match.py backend/tests/test_website_image_extractor.py backend/tests/test_menu_pipeline_quality_gate.py` -> 44 passed.
- `/Users/angelowashington/CRAVE/venv/bin/python -m pytest -q backend/tests/test_r2_client.py backend/tests/test_video_upload_pipeline_end_to_end.py` -> 7 passed.
- `/Users/angelowashington/CRAVE/venv/bin/python -m pytest -q backend/tests` -> 1024 passed, 2 skipped.
- Production menu preview -> found=3, missing=0, inactive=0.
- Production menu run with exact `--confirm-count 3` -> attempted=3,
  materialized=0, no_menu=3, errors=0.
- Production image preview -> found=2, existing image blockers=0.
- Production image run with exact `--confirm-count 2` -> attempted=2,
  staged=0, publicly_visible=0.
- `git diff --check` -> clean.

## Known gaps / risks

- The menu quality fix is demonstrated as a safety improvement, not a recall
  improvement. Recurring menu enrichment should remain disabled.
- The image browser fallback did not find either target. Recurring image
  ingestion should remain disabled.
- The R2 production recursion fix is code/test verified only; it still needs
  independent review, deployment, and a one-object quarantined retry.
- Exact production IDs remain in the dated evidence doc. Do not publish/push
  this branch unless the human explicitly approves that repository disclosure.

## Next action

Review `bf0b08c..cff3107`, especially the R2 signed-HTTP change and the updated
PR #122 test boundary. Do not call either acquisition pipeline "coverage
verified": both current-main canaries safely produced zero new content.
