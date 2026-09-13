# CRAVE UI V2 Visual Audit

Status date: September 13, 2026  
Status: first implementation audit  
Branch: `codex/ui-v2-visual-refresh`

## Summary

CRAVE already has a mostly dark app shell. The real gap is not “make the app dark”; it is replacing the old cyan action/brand language with the warmer mockup system and preventing a single amber token from carrying every possible meaning.

The biggest risk is not backend breakage. The biggest risk is a half-migrated visual system:

- old cyan left in active controls;
- amber used for warning/destructive/hard-constraint by accident;
- white text placed on amber CTAs;
- black one-off media overlays retaining the old cold look;
- selected Map pins relying only on color;
- mockup artifacts living outside git.

## Current repo finding

Latest `main` did not contain the local Search/Map mockup docs/assets that had been used in prior design discussions. This branch adds the relevant target artifacts to `docs/design/` before implementation so future work is traceable.

## Current token inventory

`frontend/src/constants/colors.ts` previously had one flat color object:

- `primary #38BDF8`
- `background #0A0A0A`
- `surface #1A1A1A`
- `surfaceElevated #252525`
- `border #2A2A2A`
- `text #FFFFFF`
- semantic `success`, `warning`, `error`
- tier colors

`Colors.primary` was overloaded across:

- brand wordmarks;
- CTA fill;
- active tabs;
- selected chips;
- map clusters;
- link text;
- loading spinners;
- section accents;
- save/filter emphasis.

## Static audit counts before first pass

From the clean worktree before token/component edits:

- `Colors.primary` appeared in 33 frontend files.
- raw hex literals appeared in 14 frontend files.
- `rgba(...)` overlays appeared in 16 frontend files.

These are not all bugs. They are migration leads.

## Post first implementation sweep

After the token foundation and shared-component pass:

- old cyan `#38BDF8`: **0** frontend occurrences;
- `Colors.primary` callers: **28** files, down from 33;
- raw hex literal files: **13**, down from 14;
- raw `rgba/rgb` overlay files: **11**, down from 16.

`Colors.primary` remains as a compatibility alias for amber. Remaining callers
are not automatically wrong, but each should be migrated to a more specific
semantic token when that file is next edited.

## Highest-priority shared components

Migrated or targeted first:

- `frontend/src/constants/colors.ts`
- `frontend/app/(tabs)/_layout.tsx`
- `frontend/src/components/PlaceCard.tsx`
- `frontend/src/components/PlaceCardCompact.tsx`
- `frontend/src/components/MapMarker.tsx`
- `frontend/src/screens/MapScreenCore.tsx`
- `frontend/src/components/CitySelectorStrip.tsx`
- `frontend/src/components/FilterSheet.tsx`
- `frontend/src/components/ShareLinkSheet.tsx`
- `frontend/src/components/Toast.tsx`
- `frontend/src/components/EmptyState.tsx`

## Screen-level audit notes

### Tabs

Current `main` already hides Map as a permanent tab and includes Rank/Profile, so no navigation surgery is needed in this visual pass. The FAB and active tab color need semantic token migration.

### Search / Map

Search/Map remain the first screen propagation target. Important correction: current Map code already supports a Search handoff mode using the Search-owned candidate set. The migration should improve visual state and accessibility without reopening that product contract.

Confirmed visual gap fixed in this branch: selected map pins previously had no non-color affordance. `MapMarkerDot` now supports a selected state with size, border, and stem treatment.

### Feed

Feed is already dark and card-based. It should benefit from shared token/card changes before deeper screen polish.

### Place Detail / Rank

These are among the closest to the food-led direction. They should be polished after Search/Map validates the token system.

### Craves / Profile / Settings / Add Spot / Food Evidence

Mostly dark already, but still utility/dashboard-like in places. These should be cleaned after shared tokens and core journey screens to avoid churn.

## First-pass fixes implemented

- Added UI V2 semantic tokens while preserving legacy token names.
- Swapped global primary from cyan to warm amber.
- Added `onPrimary`, `onActionPrimary`, selected/chip/media/scrim/map semantic roles.
- Updated selected chips and CTA text to avoid white-on-amber contrast problems.
- Replaced raw black card overlays in primary cards with media scrim tokens.
- Added warm missing-media fallback surfaces.
- Added non-color selected Map pin affordance.
- Added mockup target docs/assets to the branch.
- Migrated common sheet backdrops to `sheetScrim`.
- Migrated selected city/filter/template/share chips to selected/chip tokens.
- Migrated core CTA text on amber to `onActionPrimary`.
- Propagated Search result hierarchy one step toward the north star: the first
  result now renders as a dominant food-forward `PlaceCard`, while supporting
  results remain compact rows. Ranking/order is unchanged.

## Remaining known gaps after first pass

- 28 `Colors.primary` callers remain and should be migrated to semantic roles in follow-up sweeps.
- 11 files still contain raw `rgba/rgb` overlays, mostly media/special-effect layers.
- Search/Map screen composition is partially propagated but does not yet fully
  match the north star.
- No simulator/device screenshots captured yet in this environment.
- Dynamic Type, VoiceOver order, and reduced-motion proof remain open.
- Some raw color literals are legitimate but need review/documentation.

## Next implementation sweeps

1. Replace remaining high-risk `Colors.primary` callers with semantic tokens.
2. Move sheet/media overlays to `sheetScrim`, `mediaScrim`, or `mediaScrimSoft`.
3. Propagate Search/Map visual structure using existing product behavior.
4. Run full type/test verification.
5. Generate screenshots or document local blocker.
6. Re-audit raw colors, old cyan, touch targets, and accessibility states.
