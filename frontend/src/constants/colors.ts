// src/constants/colors.ts
export const Colors = {
  // UI chrome
  primary:         '#38BDF8',
  background:      '#0A0A0A',
  surface:         '#1A1A1A',
  surfaceElevated: '#252525',
  border:          '#2A2A2A',
  text:            '#FFFFFF',
  // Bumped from #888888 (2026-08-26) -- the old value cleared AA-normal
  // (4.5:1) on `background`/`surface` but fell to 4.32:1 on
  // `surfaceElevated`, the one surface where it actually mattered most
  // (see ACCESSIBILITY_CONTRAST_AUDIT.md). #8c8c8c clears 4.5:1 against
  // all three surfaces (4.56:1 on the tightest, surfaceElevated) with a
  // 4-unit change invisible as a design shift.
  textSecondary:   '#8C8C8C',
  // textMuted (#555555, ~2-2.7:1 against every surface) fails WCAG AA
  // outright -- never use it for text or informational icons. The one
  // legitimate remaining use is settings.tsx's two intentionally
  // *disabled* "Coming soon" rows: WCAG 1.4.3 explicitly exempts inactive
  // UI components from the contrast minimum, and those rows are paired
  // with accessibilityState={{disabled:true}}, not relying on color
  // alone. See ACCESSIBILITY_CONTRAST_AUDIT.md for the full audit this
  // fix closes out.
  textMuted:       '#555555',
  // Semantic
  success:         '#30D158',
  warning:         '#FF9F0A',
  error:           '#FF453A',
  // Tier — canonical values, imported by scoring.ts and map.tsx
  tierCravePick:   '#FF4D00',
  tierGem:         '#FFB800',
  tierSolid:       '#4CAF50',
  tierNew:         '#666666',
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
