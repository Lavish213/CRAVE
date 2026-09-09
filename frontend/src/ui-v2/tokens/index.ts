import { Colors, Radius, Shadows, Spacing, Typography } from '../../constants/colors';

/**
 * UI V2 uses semantic tokens as the only visual-value API consumed by new
 * primitives/components. Legacy constants stay behind this compatibility
 * boundary during migration.
 *
 * OPEN-VISUAL-01: this warm accent is intentionally marked provisional until
 * the UI Lab is reviewed against real food photography and contrast. Screens
 * must never import this literal or create their own replacement.
 */
export const provisionalAccent = '#F5A623' as const;

export const uiColors = {
  surface: {
    canvas: Colors.background,
    primary: Colors.surface,
    elevated: Colors.surfaceElevated,
    overlay: '#161616',
    photoScrimStrong: 'rgba(0, 0, 0, 0.68)',
    photoScrimSoft: 'rgba(0, 0, 0, 0.36)',
    selected: 'rgba(245, 166, 35, 0.12)',
  },
  text: {
    primary: Colors.text,
    secondary: Colors.textSecondary,
    inverse: Colors.background,
    disabled: Colors.textMuted,
    brand: provisionalAccent,
    positive: Colors.success,
    uncertain: Colors.warning,
    destructive: Colors.error,
    protected: Colors.primary,
  },
  accent: {
    brand: provisionalAccent,
    primaryAction: provisionalAccent,
    selected: provisionalAccent,
  },
  status: {
    positive: {
      foreground: Colors.success,
      background: 'rgba(48, 209, 88, 0.10)',
      border: 'rgba(48, 209, 88, 0.44)',
    },
    uncertain: {
      foreground: Colors.warning,
      background: 'rgba(255, 159, 10, 0.10)',
      border: 'rgba(255, 159, 10, 0.44)',
    },
    destructive: {
      foreground: Colors.error,
      background: 'rgba(255, 69, 58, 0.10)',
      border: 'rgba(255, 69, 58, 0.44)',
    },
    protected: {
      foreground: Colors.primary,
      background: 'rgba(56, 189, 248, 0.10)',
      border: 'rgba(56, 189, 248, 0.44)',
    },
    neutral: {
      foreground: Colors.textSecondary,
      background: Colors.surfaceElevated,
      border: Colors.border,
    },
  },
  border: {
    subtle: Colors.border,
    strong: '#3A3A3A',
    selected: provisionalAccent,
    positive: 'rgba(48, 209, 88, 0.44)',
    uncertain: 'rgba(255, 159, 10, 0.44)',
    destructive: 'rgba(255, 69, 58, 0.44)',
    protected: 'rgba(56, 189, 248, 0.44)',
  },
  catalogTier: {
    cravePick: Colors.tierCravePick,
    gem: Colors.tierGem,
    solid: Colors.tierSolid,
    new: Colors.tierNew,
  },
} as const;

export const uiSpace = {
  xs: Spacing.xs,
  sm: Spacing.sm,
  md: Spacing.md,
  lg: Spacing.lg,
  xl: Spacing.xl,
  xxl: Spacing.xxl,
  controlInset: Spacing.md,
  cardInset: Spacing.lg,
  sectionGap: Spacing.xl,
  screenGutter: Spacing.lg,
} as const;

export const uiRadius = {
  control: Radius.md,
  card: Radius.card,
  media: Radius.sm,
  pill: Radius.full,
  sheet: Radius.card,
} as const;

export const uiType = Typography;

export const uiElevation = {
  card: Shadows.card,
  control: Shadows.control,
  floating: Shadows.floating,
  sheet: Shadows.sheet,
} as const;

export const uiMotion = {
  instant: 0,
  fast: 120,
  standard: 220,
  deliberate: 320,
  press: 120,
  selection: 180,
  feedback: 180,
  sheet: 280,
} as const;

export const uiControl = {
  minTarget: 44,
  disabledOpacity: 0.46,
  pressedOpacity: 0.76,
} as const;

export const uiMedia = {
  heroAspectRatio: 4 / 3,
  supportingAspectRatio: 16 / 10,
  compactSize: 72,
} as const;

export type UiTextTone =
  | 'primary'
  | 'secondary'
  | 'brand'
  | 'positive'
  | 'uncertain'
  | 'destructive'
  | 'protected'
  | 'disabled'
  | 'inverse';

export type UiSurfaceTone = 'canvas' | 'primary' | 'elevated' | 'overlay' | 'selected';
export type UiTypographyRole = keyof typeof uiType;
