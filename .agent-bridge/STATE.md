# Active agent state

Status: **UI V2 foundation claimed and in progress** (user-authorized 2026-09-08). Product implementation Waves 0-7 remain merged baseline. Wave 8 is not claimed by this task. The prior Penpot/Figma design track is superseded for this UI V2 effort by the user's explicit direction to use the production design system + UI Lab as the design bridge.
Owner: ChatGPT (user-directed execution)
Branch: `chatgpt/ui-v2-foundation`
Base SHA: `1199e27c6ba9f00ac21e1eaf80d482ee38b5937e`
Scope: UI V2 foundation and Search/Map pilot only.

## Locked execution order

`UIV2-00 Repository UI Census → UIV2-01 Semantics → UIV2-02 Tokens → UIV2-03 Primitives → UIV2-04 Product Components → UIV2-05 UI Lab → UIV2-06 Search/Map Pilot → runtime certification`

No visual production code may begin before UIV2-00 is complete. Codex/agents may resolve implementation mechanics, but may not silently resolve product, UX, IA, visual-design, permission, data-semantic, or interaction ambiguity.

## Allowed files for the active foundation task

- `docs/ui-v2/**`
- `.agent-bridge/STATE.md`
- `.agent-bridge/codex-to-claude.md` only for final handoff if needed

No existing frontend production file is locked for edits during UIV2-00/01/02 documentation work. Later implementation phases must explicitly expand this list before touching production code.

## Verification plan

- Confirm the complete `frontend/app/**` route tree and `frontend/src/**` UI/component inventory against current `main`.
- Audit current design primitives/tokens against `frontend/src/constants/colors.ts`, `CRAVE_DESIGN_SYSTEM.md`, `CRAVE_COMPONENT_REGISTRY.md`, and current Search/Map implementation.
- Produce a per-surface migration classification: Keep / Restyle / Rebuild / Merge / Adapt / Retire / Blocked / Investigate.
- Document semantic and token contracts before any visual code.
- For later code phases: `cd frontend && npx tsc --noEmit`; `cd frontend && npx jest --ci`; required CI/CodeQL; UI/device evidence only after implementation.

## Explicit exclusions

- Wave 8 Posting/Private Logging product implementation.
- Backend/data-coverage canaries and production DB work.
- Reservation/order integrations.
- New product semantics not already resolved by canonical doctrine or the approved Search/Map V1.5 direction.
- Claims of device/runtime accessibility verification before executable UI exists.

## Baseline facts preserved

- Waves 0-4 merged.
- Wave 5 Search contract complete/certified; contextual Map has one previously tracked backend direct-mode ranking gap.
- Wave 6 Craves complete.
- Wave 7 Place Detail relationship hierarchy complete.
- Current `main` when claimed: `1199e27c6ba9f00ac21e1eaf80d482ee38b5937e` (merge PR #227).

## Next action

Complete UIV2-00 census artifacts on this branch, audit them, then advance to UIV2-01/02. Do not touch production UI code until those artifacts are internally consistent and the migration map names exact owners/targets.
