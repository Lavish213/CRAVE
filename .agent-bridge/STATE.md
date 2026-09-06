# Active agent state

Status: review-ready
Owner: Codex
Branch: codex/phase6-telemetry-location-async
Base SHA: 9ce1da834483bf7792d616f12527b683507b44b8 (main, post-Phase-5 squash merge -- PR #134)
Scope: Phase 6 of `CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_EXECUTION_SPEC.md` -- Telemetry, Location & Async Truth.
PR: #135

## Phase 6 result

The Phase-6 implementation is complete and verified on the code candidate immediately before this handoff commit. No Phase-7 implementation is included.

### Confirmed failures fixed

1. **Feed / Decision Session exposure semantics**
   - Removed retrieval-time impression logging.
   - Feed places and Decision Session cards now share one FlashList viewability contract.
   - Disabled Trending / Recommendations consumers perform zero hidden network work.

2. **Map exposure + identity semantics**
   - Fetched candidates are no longer treated as impressions.
   - Only visible singleton pins inside the current viewport become impressions.
   - Offscreen 1.6x prefetch-ring candidates and cluster-hidden children remain unexposed.
   - Filtering happens before exposure.
   - Click position is tied to the currently visible pin set.
   - Loaded feature sets now carry an explicit `city:*` / `saved:<user>` context key so an old city's/account's pins cannot be rendered or relabeled during a context transition.
   - Non-security analytics session IDs no longer use `Math.random()`; this resolved the CodeQL weak-randomness finding.

3. **Craves async truth + exposure**
   - Manual-added-place secondary retrieval has explicit loading/error/loaded-for-user truth.
   - Secondary failure no longer collapses to `[]` or erases stale successful data.
   - A true empty account is legal only after all required current-user resources have settled successfully.
   - Saved, matched-share, and resolved-manual-place impressions now require actual row viewability.

4. **Location freshness / permission lifecycle**
   - Shared location now has an explicit 5-minute freshness policy.
   - Foreground activation revalidates permission and refreshes stale granted coordinates.
   - OS-level permission revocation is detected instead of leaving the session permanently `granted`.
   - Add Spot distinguishes requestable denial from permanently blocked permission and offers Open Settings for the blocked case.

5. **Recommendation learning-event durability**
   - Impression/click observations remain best-effort telemetry.
   - Confirmed save/unsave outcomes use a persisted AsyncStorage outbox with `client_event_id` dedupe.
   - Durable events are account-owned and only flush under their owning authenticated account.
   - Save/unsave mutations pass the user ID captured at mutation start, closing the race where Account A's request finishes after switching to Account B.
   - Offline save/unsave retries preserve the same owner and client event ID through eventual confirmation.
   - Explicit recovery flushes are awaitable; automatic failed durable sends retry after backoff.
   - Rank remains backend-owned/transactional and was not duplicated into the client outbox.

6. **Root error recovery**
   - Root recovery now delegates Retry to Expo Router SDK55's route ErrorBoundary retry contract instead of merely clearing a local boolean boundary state.

### Verified healthy / intentionally preserved

- Search already used a 50% / 250ms FlashList viewability contract with per-query exposure dedupe; no Search rewrite was needed.
- Phase 1-5 identity, ranking, video, authorization, and transactional contracts were preserved.
- Standard `.github/workflows/ci.yml` is restored exactly to `main`; the temporary Jest diagnostics workflow used during convergence is not part of the final diff.

## Regression coverage added or updated

- `frontend/src/hooks/useLocation.test.ts`
- `frontend/__tests__/add-spot.test.tsx`
- `frontend/__tests__/feed.test.tsx`
- `frontend/__tests__/map-instrumentation.test.tsx`
- `frontend/__tests__/craves.test.tsx`
- `frontend/__tests__/root-error-boundary.test.tsx`
- `frontend/src/hooks/useTrending.test.tsx`
- `frontend/src/hooks/useRecommendations.test.tsx`
- `frontend/src/utils/recommendationEventQueue.test.ts`
- `frontend/src/stores/cravesStore.test.ts`

## Verification

Final code candidate before this handoff commit (`85a120af215459c966c81e76e7651b5ed1054c13`):

- Frontend TypeScript: **PASS**
- Frontend Jest: **396 / 396 PASS**, 39 suites
- Backend SQLite/syntax/import/tests/migration-head gate: **PASS**
- Backend real Postgres migration chain + downgrade/re-upgrade + tests: **PASS**
- Conflict-marker guard: **PASS**
- Dependency vulnerability scan job step: **PASS**
- CodeQL: **PASS**
- Open inline review threads: **0**
- Prior CodeQL weak-randomness thread: **resolved**

Because this handoff update itself changes the PR head, CI/CodeQL must be rechecked on the final documentation head before merge. No code change is expected from that rerun unless a genuine new finding appears.

## Residuals / manual verification

These are not represented as automated proof and remain release-level/device work for Phase 7:

- Real-device foreground/background location behavior on current iOS and Android.
- Permanently blocked permission -> Settings round trip on both platforms.
- VoiceOver/TalkBack and Dynamic Type behavior.
- Offline/process-restart durable-outbox behavior on a physical device.
- Performance profiling and store privacy/release declarations.

No unresolved Phase-6 P0/P1 code defect is currently known after automated verification. This is not a claim that the entire app is defect-free.

## Files changed in Phase 6

Primary production files:

- `frontend/app/(tabs)/index.tsx`
- `frontend/app/(tabs)/map.tsx`
- `frontend/app/(tabs)/craves.tsx`
- `frontend/app/add-spot.tsx`
- `frontend/app/_layout.tsx`
- `frontend/src/hooks/useLocation.ts`
- `frontend/src/hooks/useTrending.ts`
- `frontend/src/hooks/useRecommendations.ts`
- `frontend/src/stores/cravesStore.ts`
- `frontend/src/utils/recommendationEventQueue.ts`

Plus the regression tests listed above and Phase-6 agent-bridge progress/handoff documentation.

## Merge / next-phase gate

1. Re-run CI + CodeQL on the final handoff head.
2. Mark PR #135 ready for review.
3. Re-read all current review threads/comments; treat new findings as hypotheses and verify before changes.
4. If code changes, repeat full CI + CodeQL.
5. Merge PR #135 only when final head is green and no actionable verified review finding remains.
6. Pull/refetch updated `main` and record the Phase-6 merge SHA.
7. Only then create a fresh Phase-7 branch (`codex/phase7-release-hardening`) from that exact merged `main` SHA.
8. Do not stack Phase 7 on this branch.
