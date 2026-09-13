# H-20260912-social-share-reliability

Status: ready-for-review
Owner: Codex
Branch: codex/crave-social-share-loop
Base SHA: 7bf81bd
Commit SHA: ca0b6c2b43bda205ebb5b50e4e88d5487f6216bd
Allowed next files: backend/app/workers/share_parser_worker.py, backend/app/api/v1/routes/saves.py, backend/app/db/models/share_save_preference.py, backend/alembic/versions/e2f3a4b5c6d7_add_share_save_preferences.py

## Outcome

High-confidence social-share matches now persist their normal Save in the
same transaction as the match and signal. The personal map already derives
from normal Saves, so no duplicate map state was added.

`share_save_preferences` records an explicit unsave per user/place. Historic
partial matches are reconciled in bounded worker batches, but only when a
normal save is missing and no user opt-out exists. An explicit save clears the
opt-out. Account deletion removes these preference rows.

## Verification

- `DATABASE_URL=sqlite:////private/tmp/crave-social-share-migration.db alembic upgrade head` → passed.
- `... alembic downgrade c4d5e6f7a8b9` then `... alembic upgrade head` → passed.
- `python -m pytest tests/test_share_parser_auto_save.py tests/test_share_save_preference.py tests/test_account_deletion_service.py -q` → `14 passed`.
- `python -m compileall -q app` and `python -c 'import app.main'` → passed.
- `python -m pytest -q` → `1120 passed, 2 skipped`.

## Known gaps / risks

- This is backend reliability only. Native Share Sheet support, Craves status
  polling/UI, ambiguous-match confirmation, and provider/Railway validation
  remain separate scoped work.
- The worker repair loop runs only when the scheduler is enabled in production;
  deployment configuration still needs its own evidence.

## Next action

Review the diff and migration; open a PR against `main`, request CodeRabbit,
and merge only after required checks pass.
