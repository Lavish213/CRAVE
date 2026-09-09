# Active agent state

Status: **UI V2 foundation claimed and in progress** (user-authorized 2026-09-08). UIV2-00 Repository Census, UIV2-01 Semantics, and UIV2-02 Token Contract are complete on `chatgpt/ui-v2-foundation`. UIV2-03 Primitives is now active. Product implementation Waves 0-7 remain merged baseline. Wave 8 is not claimed by this task. The prior Penpot/Figma design track is superseded for this UI V2 effort by the user's explicit direction to use the production design system + UI Lab as the design bridge.
Owner: ChatGPT (user-directed execution)
Branch: `chatgpt/ui-v2-foundation`
Base SHA: `1199e27c6ba9f00ac21e1eaf80d482ee38b5937e`
Scope: UI V2 foundation and Search/Map pilot only.

## Locked execution order

`UIV2-00 Repository UI Census → UIV2-01 Semantics → UIV2-02 Tokens → UIV2-03 Primitives → UIV2-04 Product Components → UIV2-05 UI Lab → UIV2-06 Search/Map Pilot → runtime certification`

No visual production code began before UIV2-00 completed. Agents may resolve implementation mechanics, but may not silently resolve product, UX, IA, visual-design, permission, data-semantic, or interaction ambiguity.

## Allowed files for the active foundation task

- `docs/ui-v2/**`
- `frontend/src/ui-v2/**`
- `frontend/app/dev/ui-v2.tsx` once UIV2-05 begins
- `.agent-bridge/STATE.md`
- `.agent-bridge/codex-to-claude.md` only for final handoff if needed

No legacy production Search/Map file is yet authorized for edits. UIV2-06 must explicitly expand this list before touching `SearchScreen.tsx`, `MapScreenCore.tsx`, or existing shared components.

## Verification plan

- TypeScript: `cd frontend && npx tsc --noEmit`.
- Frontend tests: `cd frontend && npx jest --ci`.
- Required GitHub CI / CodeQL after PR creation.
- UI/device accessibility evidence only after executable UI exists.

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

## Next action

Implement UIV2-03 tokens/primitives inside the isolated `frontend/src/ui-v2/**` namespace, then verify before proceeding to product components. The exact warm accent literal remains a visible provisional token until UI Lab/real-photo calibration closes `OPEN-VISUAL-01`.
