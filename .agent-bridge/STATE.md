# Active agent state

Status: **UI V2 Search/Map pilot active** (user-authorized 2026-09-08). UIV2-00 Repository Census, UIV2-01 Semantics, UIV2-02 Tokens, UIV2-03 Primitives, UIV2-04 Product Components, and the initial UIV2-05 UI Lab are implemented on `chatgpt/ui-v2-foundation`. Foundation TypeScript and the full frontend Jest suite are green in PR #228 CI at commit `2297070b0840491ca87bec35efdb6f914fc0a1bb`. UIV2-06 Search/Map pilot is now authorized. Product implementation Waves 0-7 remain merged baseline. Wave 8 is not claimed by this task.
Owner: ChatGPT (user-directed execution)
Branch: `chatgpt/ui-v2-foundation`
Base SHA: `1199e27c6ba9f00ac21e1eaf80d482ee38b5937e`
PR: #228 (draft)
Scope: UI V2 foundation and Search/Map pilot only.

## Locked execution order

`UIV2-00 Repository UI Census → UIV2-01 Semantics → UIV2-02 Tokens → UIV2-03 Primitives → UIV2-04 Product Components → UIV2-05 UI Lab → UIV2-06 Search/Map Pilot → runtime certification`

No visual production code began before UIV2-00 completed. Agents may resolve implementation mechanics, but may not silently resolve product, UX, IA, visual-design, permission, data-semantic, or interaction ambiguity.

## Allowed files for active UIV2-06

- `docs/ui-v2/**`
- `frontend/src/ui-v2/**`
- `frontend/app/dev/ui-v2.tsx`
- `frontend/src/screens/SearchScreen.tsx`
- `frontend/src/screens/MapScreenCore.tsx`
- `frontend/src/components/MapBottomSheet.tsx` only as a UI V2 composition bridge
- `frontend/src/components/MapMarker.tsx` only as a compatibility adapter/retirement bridge
- `frontend/src/components/FilterSheet.tsx` only if needed for UI V2 primitive/token consumption without semantic changes
- Search/Map/UI-V2 tests
- `.agent-bridge/STATE.md`
- `.agent-bridge/codex-to-claude.md` only for final handoff if needed

Do not touch Feed, Craves, Rank, Place Detail, Posting, Profile/Taste, backend ranking/data, or unrelated legacy routes during this pilot.

## Verification evidence so far

PR #228 CI against foundation commit `2297070b0840491ca87bec35efdb6f914fc0a1bb`:
- conflict-marker guard: green
- frontend TypeScript: green
- frontend Jest suite: green
- backend checks still running at the time this state advanced; no backend files are changed by this UI task
- CodeQL is required before merge

Runtime/device accessibility remains **unverified** until executable UI is tested. UI Lab states are design/implementation proof only.

## Explicit exclusions

- Wave 8 Posting/Private Logging product implementation.
- Backend/data-coverage canaries and production DB work.
- Reservation/order integrations.
- New product semantics not already resolved by canonical doctrine or approved Search/Map V1.5 direction.
- Claims of device/runtime accessibility verification before executable UI exists.

## Baseline facts preserved

- Waves 0-4 merged.
- Wave 5 Search contract complete/certified; contextual Map has one previously tracked backend direct-mode ranking gap.
- Wave 6 Craves complete.
- Wave 7 Place Detail relationship hierarchy complete.
- Current `main` when claimed: `1199e27c6ba9f00ac21e1eaf80d482ee38b5937e` (merge PR #227).

## Open visible design unknown

`OPEN-VISUAL-01`: exact warm orange/gold production accent calibration. Semantic role is locked; current literal is explicitly provisional until actual UI Lab + real-photo + contrast/device review. This is not permission for screen-local colors.

## Next action

Migrate Search first while preserving its already-certified behavior and data contracts, then Map while preserving exact Search candidate handoff, explicit Search-this-area behavior, and list-equivalent location fallback. Re-run CI after each meaningful pilot boundary. Do not certify visual/runtime accessibility until actual runtime evidence exists.
