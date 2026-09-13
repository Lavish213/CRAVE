// src/constants/colors.ts
export const Colors = {
  // CRAVE UI V2 visual foundation.
  //
  // Keep the legacy keys (`primary`, `background`, etc.) while adding
  // meaning-first aliases. That lets the app move toward the mockup's warm
  // food-led direction without forcing every caller to treat amber as "brand,
  // selection, warning, cluster, CTA, and proof" at the same time.
  primary:         '#F4A845',
  onPrimary:       '#080604',
  brand:           '#F4A845',
  brandSoft:       '#3A2815',
  brandMuted:      '#B97928',
  background:      '#050807',
  backgroundRaised:'#0A100E',
  surface:         '#101715',
  surfaceElevated: '#18211E',
  surfaceWarm:     '#241914',
  border:          '#2B3833',
  borderSubtle:    '#1E2925',
  text:            '#FFF8EF',
  // Bumped from #888888 (2026-08-26) -- the old value cleared AA-normal
  // (4.5:1) on `background`/`surface` but fell to 4.32:1 on
  // `surfaceElevated`, the one surface where it actually mattered most
  // (see ACCESSIBILITY_CONTRAST_AUDIT.md). #8c8c8c clears 4.5:1 against
  // all three surfaces (4.56:1 on the tightest, surfaceElevated) with a
  // 4-unit change invisible as a design shift.
  textSecondary:   '#B8B0A6',
  // textMuted (#555555, ~2-2.7:1 against every surface) fails WCAG AA
  // outright -- never use it for text or informational icons. The one
  // legitimate remaining use is settings.tsx's Notifications row when its
  // status is genuinely "unavailable" (onPress unset, non-interactive):
  // WCAG 1.4.3 explicitly exempts inactive UI components from the
  // contrast minimum, and that row's tint change is paired with an
  // unset onPress, not relying on color alone. See
  // ACCESSIBILITY_CONTRAST_AUDIT.md for the full audit this fix closes
  // out.
  textMuted:       '#7B736A',
  textDisabled:    '#5A554F',
  actionPrimary:   '#F4A845',
  onActionPrimary: '#080604',
  actionSecondary: '#1B2421',
  selectedBg:      '#F4A845',
  selectedText:    '#080604',
  selectedBorder:  '#F7C16E',
  chipBg:          '#141D1A',
  chipActiveBg:    '#2F2114',
  chipActiveText:  '#FFD79A',
  mediaScrim:      'rgba(0,0,0,0.68)',
  mediaScrimSoft:  'rgba(0,0,0,0.42)',
  sheetScrim:      'rgba(0,0,0,0.68)',
  overlayDim:      'rgba(0,0,0,0.54)',
  onMedia:         '#FFFFFF',
  // Semantic
  success:         '#30D158',
  warning:         '#F59E0B',
  stale:           '#DCA34B',
  hardConstraint:  '#EF4444',
  destructive:     '#DC2626',
  error:           '#FF453A',
  mapSelected:     '#F4A845',
  mapUnselected:   '#A7B0AA',
  mapCluster:      '#F4A845',
  // Tier — canonical values, imported by scoring.ts and map.tsx
  tierCravePick:   '#FF7A1A',
  tierGem:         '#F4A845',
  tierSolid:       '#5DCC7A',
  tierNew:         '#7D8983',
} as const;

export type ColorKey = keyof typeof Colors;

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const Radius = {
  sm: 8,
  md: 12,
  card: 14,
  pill: 20,
  full: 9999,
} as const;

/**
 * Canonical text roles from CRAVE_DESIGN_SYSTEM.md §2.
 *
 * New or edited text styles consume these roles rather than introducing raw
 * font sizes. `display` remains reserved for genuine hero moments such as
 * Rank's score reveal.
 */
export const Typography = {
  micro: {
    fontSize: 11,
    fontWeight: '500' as const,
    lineHeight: 14,
    letterSpacing: 0,
  },
  caption: {
    fontSize: 12,
    fontWeight: '500' as const,
    lineHeight: 16,
    letterSpacing: 0,
  },
  body: {
    fontSize: 14,
    fontWeight: '400' as const,
    lineHeight: 20,
    letterSpacing: 0,
  },
  label: {
    fontSize: 16,
    fontWeight: '600' as const,
    lineHeight: 22,
    letterSpacing: 0,
  },
  subtitle: {
    fontSize: 18,
    fontWeight: '700' as const,
    lineHeight: 24,
    letterSpacing: 0,
  },
  title: {
    fontSize: 22,
    fontWeight: '800' as const,
    lineHeight: 28,
    letterSpacing: -0.2,
  },
  headline: {
    fontSize: 26,
    fontWeight: '900' as const,
    lineHeight: 32,
    letterSpacing: -0.3,
  },
  display: {
    fontSize: 56,
    fontWeight: '900' as const,
    lineHeight: 60,
    letterSpacing: -0.5,
  },
} as const;

export type TypographyRole = keyof typeof Typography;

// Elevation tiers — before this, every floating surface (map controls,
// Toast, MapBottomSheet) hand-typed its own shadowColor/Opacity/Radius/
// elevation with no shared logic, and cards (PlaceCard etc.) had no shadow
// at all — just a 1px border on flat black, which is why they read as flat
// cutouts rather than cards. These three tiers are the values already in
// use across the app (map.tsx's controls, Toast, MapBottomSheet) given
// names so new surfaces reuse a real tier instead of inventing a fourth
// arbitrary one; `card` is the one genuinely new tier, for surfaces that
// previously had none.
export const Shadows = {
  card: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 3,
    elevation: 2,
  },
  control: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 4,
  },
  floating: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 10,
  },
  sheet: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 16,
  },
} as const;
