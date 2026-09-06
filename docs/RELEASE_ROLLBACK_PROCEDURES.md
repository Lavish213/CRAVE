# Release rollback and incident response procedures

Certification (the rest of this matrix) is pre-release. This document
is what happens in the hours/days immediately after — the operational
readiness gap the certification matrix itself doesn't cover. Prepare
this before submission, not after something breaks.

## 1. Backend regression discovered after deployment

- Railway keeps prior deployments; the fastest mitigation is usually
  **rolling back to the last known-good Railway deployment** via the
  Railway dashboard (Deployments tab → redeploy a prior build), not a
  new hotfix commit under pressure.
- Before rolling back, check whether the regression involves a
  database migration that already ran — a rollback that leaves the DB
  schema ahead of the rolled-back code can be worse than the original
  bug. If a migration is involved, the fix is a forward migration
  (`alembic downgrade` only if a real, tested `downgrade()` exists for
  it — per `ci.yml`'s own "newest migration downgrades and re-upgrades
  cleanly" check, this is expected to work for the newest migration,
  but confirm before relying on it for an older one).
- `GET /api/v1/debug/version` on the rolled-back deployment confirms
  which commit is actually serving traffic — don't assume the rollback
  took effect without checking.

## 2. Backend deployment must be rolled back mid-migration

- If a migration partially applied before a failure, do not attempt a
  fresh forward-fix deploy against a half-migrated schema. Assess the
  actual DB state directly (`alembic current`, `alembic heads`) before
  deciding whether to complete the migration forward or downgrade.
- This is the scenario `ci.yml`'s real-Postgres migration-chain job
  exists to catch before it ever reaches production — a production
  migration failure despite that gate passing in CI is itself a
  CI-gap finding worth a bucket-4 follow-up once the immediate
  incident is resolved.

## 3. A shipped mobile build has a critical defect

Unlike the backend, a broken mobile build **cannot be un-shipped** from
devices that already updated. Options, roughly in order of speed:

- If the defect is backend-fixable (e.g. a bad API response the app
  mishandles) without a new client build, fix the backend first — this
  is almost always faster than an app-store update cycle.
- If a genuine client-code fix is required: submit an expedited update
  through the normal App Store Connect / Play Console review process.
  Apple's expedited-review request exists for exactly this; Google
  Play's staged rollout (if used) can also be halted before it reaches
  100% of users.
- If OTA (`expo-updates`) were active this could patch JS-only fixes
  without a store review cycle — but per Phase 7's finding, this repo
  does **not** currently prove an active OTA/`expo-updates` runtime
  policy (deliberately not invented). Until that's a real, tested
  capability, treat every client fix as requiring a full store
  resubmission cycle, not an OTA push.

## 4. Credentials need rotation (a leaked key, a departing team member, a provider-side breach notice)

- Rotating any credential in
  `docs/PRODUCTION_ENVIRONMENT_MANIFEST.md` follows the same shape:
  generate the new credential at the provider (Railway/Supabase/
  Cloudflare/Google/Sentry), update the Railway/EAS environment
  variable, redeploy/rebuild as needed, then revoke the old credential
  at the provider — **in that order**, so there's no window where the
  old credential is revoked but the new one isn't live yet.
- `SECRET_KEY` rotation specifically invalidates all outstanding
  ranking-comparison tokens (`app/services/personal_ranking/
  ranking_service.py`) — expected, not a bug, but worth a heads-up if
  users are mid-ranking-flow at the moment of rotation.
- `SUPABASE_SERVICE_ROLE_KEY` rotation has no user-facing effect
  (it's only used server-side for account deletion) beyond needing
  the new value in Railway.

## 5. The store rejects the app (review rejection)

- Read the actual rejection reason before making any change — Apple/
  Google rejections cite a specific guideline; a fix aimed at the
  wrong guideline wastes another review cycle.
- Common categories worth having an instinct for: privacy-label/Data
  Safety mismatch with actual runtime behavior (this is exactly what
  `docs/PROVIDER_DATA_FLOW_INVENTORY.md` exists to keep accurate),
  a broken permission-purpose string, an account-deletion path that
  doesn't satisfy Google's current requirements (re-check against
  matrix Section 12's "final policy refresh" gate — these requirements
  do change), or a crash on launch during review (the review device/OS
  combination may differ from anything in this session's own device
  certification — if so, that's a real gap to add to
  `docs/RUNBOOK_PHYSICAL_DEVICE_CERTIFICATION.md` for next time).

## 6. Production Sentry/observability shows a spike after release

- This is the intended outcome of Section 2's Sentry certification —
  a real spike should be visible and actionable, not something
  discovered from user reports first. If it isn't visible, that's
  itself a finding: re-run `docs/SENTRY_PRODUCTION_VERIFICATION.md`.
- Triage by whether the spike is backend (fixable via Section 1 above)
  or client (Section 3 above) before deciding a response path.

## Maintenance

This document should grow with real incidents — if something happens
after release that isn't covered here, add it as a new numbered
section afterward, not just resolve it ad hoc and forget the pattern.
