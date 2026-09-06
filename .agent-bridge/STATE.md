# Active agent state

Status: in-progress
Owner: Codex
Branch: codex/phase7-release-hardening
Base SHA: 8900039a8c7c14b3db22696af6942fa7113d2dd3 (main, post-Phase-5 follow-up PR #136 squash merge)
Scope: Phase 7 of `CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_EXECUTION_SPEC.md` — Performance, Accessibility, Security, Observability, Release Certification.

## Merged baseline

- Phase 1: merged.
- Phase 2: merged.
- Phase 3: merged.
- Phase 4: merged.
- Phase 5: merged via PR #134.
- Phase 5 follow-up: PR #136 merged as `8900039a8c7c14b3db22696af6942fa7113d2dd3`; all actionable CodeRabbit findings were resolved before merge, with CI and CodeQL green.
- Phase 6: PR #135 merged as `e7e19d73e4505282abab0009f9e98edbda3d63c5` and is included in the current main baseline.

## Locked Phase-7 scope

1. Release/config truth: version/build metadata, EAS/store configuration, permission declarations, environment separation, signing/keys/config assumptions. Do not add OTA/EAS Update runtime policy unless current code/config proves OTA is actually used.
2. Security/privacy: verify server-side authorization remains intact, account deletion actually removes associated user data/UGC or documents a legitimate retention need, secrets/config/logging are safe, upload ownership is preserved, malformed inputs fail closed.
3. Observability: verify crash/unhandled-JS/API/video/auth/ranking/durable-event failure visibility and privacy-safe diagnostic context. Do not claim Sentry or any provider exists unless the repo proves it.
4. Performance: measure/audit startup, tab switching, Feed/Search/Map/Place Detail, hidden network work, query-cache ownership, list/image/map behavior. Optimize only measured or mechanically confirmed issues.
5. Accessibility: VoiceOver/TalkBack/Dynamic Type/touch-target/contrast/roles/focus/reduced-motion audit; automate what can be proven in repo, leave real-device checks explicit.
6. Dormant modules: classify empty/stub/deprecated files; do not imply capabilities that do not exist.
7. Final adversarial/release regression: multi-account, route churn, offline/reconnect, permission Settings round-trip, foreground/background, real iOS/Android where device access exists.

## Confirmed Phase-7 findings so far

- **CONFIRMED BUG — Settings version truth:** `frontend/app/settings.tsx` hardcodes `APP_VERSION = '1.0.0'` while EAS uses remote version management. UI must read actual installed native application/build metadata.
- **REJECTED / NOT CONFIGURED — OTA runtime policy:** `frontend/eas.json` defines preview/production channels, but current app config/package manifest do not prove `expo-updates`/`updates.url`/`runtimeVersion` usage. Do not invent an OTA architecture.
- **P0 RELEASE GAP — account deletion:** current backend deletion service removes only profile/follow/block plus Supabase Auth identity. It intentionally leaves rankings, Craves/hitlist data, recommendation events, activity, streaks, push tokens, reports, user-uploaded images/videos and storage objects. This conflicts with the in-app privacy promise and store account-deletion expectations unless a legitimate retention rule is explicitly defined.
- **CONFIRMED PRIVACY-POLICY MISMATCH:** in-app privacy text states immediate associated-data deletion and names Sentry crash reporting, but current repo audit has not verified Sentry integration. Policy/store declarations must match runtime behavior.
- **RELEASE CERTIFICATION GAP:** Google Play account-deletion policy requires an external web deletion path in addition to in-app deletion. This is a release/store deliverable; do not falsely mark complete from repo-only work.
- R2 exposes a real `delete_object(key)` primitive, so storage-object deletion can be implemented without a new storage system.

## Current account-owned data map under audit

Confirmed user-linked tables/fields include at least:
- `user_profiles.id`
- `user_follows.follower_id/followee_id`
- `user_blocks.blocker_id/blocked_id`
- `place_rankings.user_id`
- `activity_events.user_id` and `target_user_id`
- `user_streaks.user_id`
- `device_push_tokens.user_id`
- `recommendation_events.user_id`
- `hitlist_saves.user_id`
- `hitlist_suggestions.user_id`
- `hitlist_dedup_keys.user_id`
- `crave_items.submitted_by`
- `place_images.uploaded_by` plus `orig_key/processed_key/thumb_key`
- `place_videos.uploaded_by` plus `orig_key/processed_key/thumb_key`
- `image_reports.reporter_id`
- `video_reports.reporter_id`

This map is not yet declared complete; every model must be checked before changing deletion logic.

## Rules

- Re-verify current main/branch code before every change.
- No speculative refactors or new architecture.
- Preserve Phases 1–6 and the Phase-5 follow-up contracts.
- Treat CI/reviewer findings as hypotheses; verify before editing.
- No explicit `any` added to production frontend.
- No release/compliance claim without proof.
- Real-device/store-console requirements remain explicit residuals when this environment cannot prove them.

## Next action

Finish the complete user-owned DB/storage map, then harden account deletion with regression coverage before moving to version/config, privacy/observability, accessibility/performance, dormant-code classification, and final release gates. Do not open/merge the Phase-7 PR until scoped implementation and verification are coherent.
