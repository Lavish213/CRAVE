import React from 'react';
import { StyleSheet } from 'react-native';
import { uiColors, uiRadius, uiSpace } from '../tokens';
import { CravePressable, CraveText } from '../primitives';

export type ConstraintKind = 'protected' | 'preferred' | 'relaxed';

export interface ConstraintTokenProps {
  label: string;
  kind?: ConstraintKind;
  onRemove?: () => void;
}

export function ConstraintToken({ label, kind = 'preferred', onRemove }: ConstraintTokenProps) {
  const protectedConstraint = kind === 'protected';
  const relaxed = kind === 'relaxed';
  const foreground = protectedConstraint
    ? uiColors.status.protected.foreground
    : relaxed
      ? uiColors.status.uncertain.foreground
      : uiColors.status.neutral.foreground;
  const backgroundColor = protectedConstraint
    ? uiColors.status.protected.background
    : relaxed
      ? uiColors.status.uncertain.background
      : uiColors.status.neutral.background;
  const borderColor = protectedConstraint
    ? uiColors.status.protected.border
    : relaxed
      ? uiColors.status.uncertain.border
      : uiColors.status.neutral.border;

  return (
    <CravePressable
      onPress={onRemove}
      disabled={!onRemove}
      compactTarget={!onRemove}
      accessibilityLabel={onRemove ? `Remove ${label} constraint` : `${label} constraint`}
      accessibilityHint={protectedConstraint ? 'Protected constraint' : undefined}
      style={[
        styles.token,
        !onRemove ? styles.staticToken : null,
        { backgroundColor, borderColor },
      ]}
    >
      <CraveText role="caption" style={{ color: foreground }}>
        {protectedConstraint ? `Protected · ${label}` : relaxed ? `Relaxed · ${label}` : label}{onRemove ? '  ×' : ''}
      </CraveText>
    </CravePressable>
  );
}

const styles = StyleSheet.create({
  token: {
    alignSelf: 'flex-start',
    paddingHorizontal: uiSpace.md,
    borderRadius: uiRadius.pill,
    borderWidth: 1,
  },
  staticToken: {
    minHeight: 36,
  },
});
