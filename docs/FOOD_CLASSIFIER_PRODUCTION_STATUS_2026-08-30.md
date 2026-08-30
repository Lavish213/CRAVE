# Food classifier production status — 2026-08-30

## Verdict

**Source/deployment readiness is present, but live inference is not yet proven.**

The deployed revision contains the 12 MB TFLite model and declares
`ai-edge-litert>=1.0.0`. The video worker is running on schedule. Production
currently has zero `PlaceVideo` rows, however, so the worker has never needed
to load the interpreter or score a real upload. It would be inaccurate to call
the classifier either confirmed-working or broken from current evidence.

There is no silent heuristic fallback in this path. If the interpreter or
model cannot load, the upload is marked `failed` with
`food_classifier_unavailable`; it is not accepted using a weaker rule.

## Evidence

- Deployed Git revision inspected: `ba261a5337dee2da853abbf8240a3e31ac320988`.
- Model artifact: `backend/app/services/video/food_classifier.tflite`
  (approximately 12 MB), with `labels.txt` beside it.
- Runtime dependency: `backend/requirements.txt` declares
  `ai-edge-litert>=1.0.0`.
- Interpreter selection in `food_classifier.py`: `ai_edge_litert`, then
  `tflite_runtime`, then TensorFlow Lite; exhaustion raises
  `FoodClassifierUnavailableError`.
- Worker behavior in `video_processing_worker.py`: classifier setup errors
  become `food_classifier_unavailable` failures in both highlight selection
  and final scoring. No heuristic acceptance path exists.
- Read-only production database audit through Railway on 2026-08-30:
  - `PlaceVideo` count by status: no rows.
  - `video_processing` job runs were succeeding every roughly three minutes
    with `batch_size: 0`.
  - Other scheduler jobs continued through 22:59 UTC, proving that a scheduler
    process is active against the production database.
- The primary Railway project (`innovative-youth`) contains the web `CRAVE`
  service and Postgres. Its web-service log correctly reports
  `scheduler_embedded_disabled`; the web process is not the scheduler owner.
- Scheduler ownership was verified in a separate Railway project
  (`rare-sparkle`). Its running `CRAVE` service is deployed from the same
  revision, uses `railway.scheduler-worker.toml`, and starts with
  `cd backend && python -m app.scheduler_worker`. Its log reports
  `scheduler_worker_started jobs=10`, and its activity agrees with production
  `JobRun` timestamps. No embedded-scheduler flag should be enabled on the web
  service; doing so would create duplicate job ownership.
- Direct container SSH could not be used because this workstation has no SSH
  key configured for Railway. No key or credential was created as part of this
  read-only investigation.

## What would close the proof gap

Use a controlled, non-user test video through the real signed upload flow and
record all of the following:

1. upload reaches `pending` and the scheduled worker claims it;
2. classification returns a numeric `food_score` without an
   `food_classifier_unavailable` error;
3. processing, moderation, and notification behavior complete as designed;
4. the test record and media are removed through the project's approved,
   reversible cleanup procedure.

That is an integration/device verification task. Adding a fake success health
flag or running a different local Python environment would not prove the
production container can load the model.

## Production changes made

None. This investigation was read-only.
