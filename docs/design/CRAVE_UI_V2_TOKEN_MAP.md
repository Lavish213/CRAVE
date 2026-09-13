# CRAVE UI V2 Token Map

Status date: September 13, 2026  
Status: implementation draft  
Scope: visual-system migration only

## Target

CRAVE UI V2 adopts the Search/Map visual north star:

- dark cinematic shell;
- warm food-led amber/gold accent;
- food photography first;
- calmer chips and less dashboard chrome;
- deliberate missing-media identity states;
- semantic color separation for action, selection, uncertainty, hard constraints, and destructive actions.

This is not a new ranking, recommendation, backend, Search, or Map product contract.

## Source artifacts

- `SEARCH_MAP_V15_VISUAL_NORTH_STAR.md`
- `SEARCH_MAP_V15_SCREEN_MOCKUPS.md`
- `SEARCH_MAP_V15_PRE_PENPOT_PACKAGE.md`
- `CRAVE_CORE_5_SCREEN_MOCKUPS.md`
- matching SVG boards checked into `docs/design/`

These artifacts were local-only before this branch. UI V2 needs them committed so implementation has a durable target.

## Token strategy

Do not treat one `primary` color as every visual meaning. UI V2 keeps legacy keys for compatibility while adding semantic aliases.

| Role | Token | Value | Meaning |
| --- | --- | --- | --- |
| Brand / warm accent | `brand` | `#F4A845` | CRAVE identity, tasteful highlight |
| Primary action fill | `actionPrimary` | `#F4A845` | main CTA background |
| Text on primary action | `onActionPrimary` | `#080604` | dark text/icon on amber |
| Selection fill | `selectedBg` | `#F4A845` | selected tabs/chips/pins |
| Text on selected fill | `selectedText` | `#080604` | selected pill text |
| Selected border | `selectedBorder` | `#F7C16E` | non-color selected outline |
| Root background | `background` | `#050807` | app shell |
| Raised background | `backgroundRaised` | `#0A100E` | subtle elevated shell |
| Surface | `surface` | `#101715` | base cards/sheets |
| Elevated surface | `surfaceElevated` | `#18211E` | inputs, selected panels |
| Warm media fallback | `surfaceWarm` | `#241914` | no-photo / identity treatment |
| Text primary | `text` | `#FFF8EF` | main text |
| Text secondary | `textSecondary` | `#B8B0A6` | supporting text |
| Text muted | `textMuted` | `#7B736A` | non-critical metadata |
| Chip background | `chipBg` | `#141D1A` | neutral pills |
| Active chip background | `chipActiveBg` | `#2F2114` | warm active chips |
| Active chip text | `chipActiveText` | `#FFD79A` | text on warm chip background |
| Media scrim | `mediaScrim` | `rgba(0,0,0,0.68)` | bottom image overlays |
| Soft media scrim | `mediaScrimSoft` | `rgba(0,0,0,0.42)` | icon/pill overlays |
| Sheet scrim | `sheetScrim` | `rgba(0,0,0,0.68)` | modal backdrop |
| Stale/unknown | `stale` | `#DCA34B` | old or unverified data |
| Hard constraint | `hardConstraint` | `#EF4444` | protected requirement that cannot be silently relaxed |
| Destructive | `destructive` | `#DC2626` | delete/remove/account danger |
| Map selected | `mapSelected` | `#F4A845` | selected pin/cluster focus |
| Map unselected | `mapUnselected` | `#A7B0AA` | neutral map candidate |

## Rules

1. `Colors.primary` remains for compatibility, but new/edited code should prefer semantic roles.
2. Amber/gold means brand, selected state, or primary action only. It is not warning by default.
3. Destructive and hard-constraint states are separate.
4. Stale/unknown data is separate from destructive/error red.
5. Text/icons on amber use `onActionPrimary` or `selectedText`, not white.
6. Missing media uses `surfaceWarm`, not a broken-photo style.
7. Map selected state must be visible without relying on color alone.
8. Raw color literals should only remain for external/platform cases or documented media overlays.

## Migration order

1. Token foundation.
2. Shared selected/CTA controls.
3. Cards, media fallbacks, overlays.
4. Map marker selected/non-color state.
5. Search/Map screen propagation.
6. Feed, Place Detail, Rank polish.
7. Remaining supporting screens.
8. Final raw-color and screenshot audit.

