// src/constants/colors.ts
export const Colors = {
  // UI chrome
  primary:         '#4A90E2',
  background:      '#0A0A0A',
  surface:         '#1A1A1A',
  surfaceElevated: '#252525',
  border:          '#2A2A2A',
  text:            '#FFFFFF',
  textSecondary:   '#888888',
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
