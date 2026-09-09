import React from 'react';
import { StyleSheet, View } from 'react-native';
import { uiColors, uiRadius, uiSpace } from '../tokens';
import { CraveButton, CraveText } from '../primitives';

export type DecisionRecoveryKind = 'requiredZero' | 'preferredNoExact' | 'locationDenied' | 'locationUnavailable' | 'generic';

export interface DecisionRecoveryProps {
  kind: DecisionRecoveryKind;
  title: string;
  body: string;
  primaryLabel?: string;
  onPrimary?: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
  protectedConstraint?: string;
}

export function DecisionRecovery({
  kind,
  title,
  body,
  primaryLabel,
  onPrimary,
  secondaryLabel,
  onSecondary,
  protectedConstraint,
}: DecisionRecoveryProps) {
  const protectedState = kind === 'requiredZero';

  return (
    <View style={[styles.container, protectedState ? styles.protected : null]}>
      {protectedConstraint ? <CraveText role="micro" tone="protected">PROTECTED · {protectedConstraint}</CraveText> : null}
      <CraveText role="title">{title}</CraveText>
      <CraveText role="body" tone="secondary">{body}</CraveText>
      {(primaryLabel || secondaryLabel) ? (
        <View style={styles.actions}>
          {primaryLabel && onPrimary ? <CraveButton label={primaryLabel} onPress={onPrimary} /> : null}
          {secondaryLabel && onSecondary ? <CraveButton label={secondaryLabel} variant="secondary" onPress={onSecondary} /> : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: uiSpace.md,
    padding: uiSpace.lg,
    borderRadius: uiRadius.card,
    borderWidth: 1,
    borderColor: uiColors.border.subtle,
    backgroundColor: uiColors.surface.primary,
  },
  protected: {
    borderColor: uiColors.border.protected,
    backgroundColor: uiColors.status.protected.background,
  },
  actions: {
    gap: uiSpace.sm,
    marginTop: uiSpace.xs,
  },
});
