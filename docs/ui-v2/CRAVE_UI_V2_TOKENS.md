# CRAVE UI V2 Token Contract

**Status:** UIV2-02 canonical token contract
**Principle:** screens consume semantic tokens; primitives/components own token selection; raw visual values do not spread through screens.

## 1. Migration strategy

UI V2 does **not** throw away the existing dark system. It wraps the proven base values in semantic roles, separates concept meanings that are currently overloaded, and introduces only the minimum new roles needed by the approved Search/Map direction.

Existing `frontend/src/constants/colors.ts` remains compatibility infrastructure during migration. UI V2 code imports from `frontend/src/ui-v2/tokens`, not directly from legacy `Colors/Spacing/Radius/Typography/Shadows`.

Legacy callers are retired gradually. There is no flag-day rewrite.

## 2. Surface roles

| Token | Initial source/value | Meaning |
|---|---|---|
| `surface.canvas` | legacy `background` / `#0A0A0A` | app canvas |
| `surface.primary` | legacy `surface` / `#1A1A1A` | default content surface |
| `surface.elevated` | legacy `surfaceElevated` / `#252525` | elevated controls/secondary blocks |
| `surface.overlay` | derived dark overlay | sheets/floating overlays |
| `surface.photoScrim` | derived translucent dark | text protection over photography |
| `surface.selected` | semantic accent-tinted surface | selected/active only |

No UI V2 screen invents a new card background locally.

## 3. Text roles

| Token | Source | Meaning |
|---|---|---|
| `text.primary` | `#FFFFFF` | primary readable copy |
| `text.secondary` | `#8C8C8C` | secondary copy; existing audited contrast |
| `text.inverse` | dark | copy on bright primary action |
| `text.disabled` | existing disabled-only muted role | inactive UI only |
| `text.brand` | brand accent | rare brand emphasis |
| `text.positive` | semantic positive | confirmed/success truth |
| `text.uncertain` | semantic uncertainty | stale/uncertain truth |
| `text.destructive` | semantic destructive | error/delete/destructive |

`text.disabled` is never used for ordinary metadata.

## 4. Accent roles

UI V2 uses semantic names:

- `accent.brand`
- `accent.primaryAction`
- `accent.selected`

These intentionally resolve to one warm orange/gold family in V1. They are separate aliases so future evolution can diverge without screen rewrites.

### OPEN-VISUAL-01 — exact warm accent calibration

The approved direction is **warm orange/gold**, and the semantic role is locked. The exact production hex is not promoted to FINAL merely from prose. The first UI Lab implementation may use one provisional warm value behind `accent.brand`; it must be calibrated against real food photography and contrast before Search/Map certification. This is a visible implementation unknown, not permission for screen-local colors.

Until certification, code comments/docs must call that literal `provisionalAccent`, never `finalBrandGold`.

## 5. Status roles

Status tokens are concept-specific and never aliases of the brand accent merely for visual convenience:

- `status.positive.foreground/background/border`
- `status.uncertain.foreground/background/border`
- `status.destructive.foreground/background/border`
- `status.protected.foreground/background/border`
- `status.neutral.foreground/background/border`

Current `success`, `warning`, and `error` values are acceptable starting sources for positive/uncertain/destructive, subject to contrast checks in the UI Lab.

`protected` is a dedicated semantic role for hard constraints. It is not destructive red and not brand gold.

## 6. Border roles

- `border.subtle`
- `border.strong`
- `border.selected`
- `border.positive`
- `border.uncertain`
- `border.destructive`
- `border.protected`

Selection uses `border.selected`; recommendation quality does not.

## 7. Typography roles

UI V2 preserves the eight-role legacy scale and renames it only if necessary for ergonomic imports:

- `type.micro`
- `type.caption`
- `type.body`
- `type.label`
- `type.subtitle`
- `type.title`
- `type.headline`
- `type.display`

New/edited UI V2 styles spread a role object; they do not specify raw `fontSize`, `lineHeight`, or `fontWeight` unless the canonical token itself is being defined.

The Search/Map pilot should normally use micro through headline. `display` remains exceptional.

## 8. Spacing roles

Base spacing stays on the proven 4/8/12/16/24/32 scale:

- `space.xs`
- `space.sm`
- `space.md`
- `space.lg`
- `space.xl`
- `space.xxl`

UI V2 may add semantic aliases without adding values:

- `space.controlInset`
- `space.cardInset`
- `space.sectionGap`
- `space.screenGutter`

Aliases make intent readable while avoiding arbitrary numbers.

## 9. Radius roles

- `radius.control` → existing `md`
- `radius.card` → existing `card`
- `radius.media` → existing `sm`/card-derived approved value
- `radius.pill` → existing `pill/full` as appropriate
- `radius.sheet` → card-family radius

Cards stay editorial/sharper; pills are controls, not the universal container shape.

## 10. Elevation roles

Preserve existing shadow tiers:

- `elevation.card`
- `elevation.control`
- `elevation.floating`
- `elevation.sheet`

Map pins do not gain arbitrary shadows per state; selected emphasis is a semantic variant.

## 11. Motion roles

Add centralized durations/behavior roles:

- `motion.instant`
- `motion.fast`
- `motion.standard`
- `motion.deliberate`

And semantic transitions:

- `motion.press`
- `motion.selection`
- `motion.sheet`
- `motion.feedback`

Reduced Motion contract:

- nonessential translation/scale may collapse to opacity or instant state;
- functional confirmation remains;
- no autoplay/parallax/swipe-to-decide motion is introduced.

Exact durations live only in the token module and are tuned through the UI Lab, not copied into screens.

## 12. Media tokens

Media needs presentation roles rather than one generic image style:

- `media.heroAspect`
- `media.supportingAspect`
- `media.compactSize`
- `media.scrimStrong`
- `media.scrimSoft`
- `media.fallbackSurface`

A media token never implies that an image exists. Missing-media layout is a component variant.

## 13. Control tokens

Primitives own:

- `control.minTarget = 44`
- disabled opacity/treatment
- focus/selected border behavior
- pressed feedback
- text scaling behavior

Screens must not work around the minimum target with a visually tiny `TouchableOpacity` plus random `hitSlop` unless platform-specific behavior truly requires it.

## 14. Catalog and Rank colors remain separate namespaces

Existing catalog percentile colors remain under a dedicated compatibility namespace and are **not** promoted into general UI V2 status colors.

Personal Rank tiers remain a separate semantic namespace.

Neither can be passed to `accent.*` or `status.*` APIs.

## 15. Import boundary

Target:

```ts
import { uiColors, uiSpace, uiType, uiRadius, uiMotion } from '@/ui-v2/tokens';
```

Avoid in migrated UI V2 components:

```ts
import { Colors } from '@/constants/colors';
```

Compatibility adapters may import legacy constants internally while migration is active.

## 16. Hard rules

1. No raw hex in screens.
2. No raw `fontSize` in new/edited UI V2 screen styles.
3. No new spacing/radius value without a named token change.
4. Brand accent is not uncertainty, success, error, hard-constraint, or ordinary metadata.
5. Selection is not recommendation ranking.
6. Missing media does not reserve a broken-looking empty frame.
7. Exact accent literal remains visibly provisional until UI Lab/real-photo calibration closes OPEN-VISUAL-01.
