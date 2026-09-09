import React from 'react';
import { StyleSheet, View } from 'react-native';
import { uiColors, uiRadius, uiSpace } from '../tokens';
import { CraveText } from '../primitives';

export type EvidenceLimitationKind =
  | 'hoursStale'
  | 'menuLimited'
  | 'photoUnavailable'
  | 'fewMatchingSaves'
  | 'tasteUnverified';

const copy: Record<EvidenceLimitationKind, string> = {
  hoursStale: 'Hours not recently verified',
  menuLimited: 'Limited menu information',
  photoUnavailable: 'Photo unavailable',
  fewMatchingSaves: 'Few matching saves yet',
  tasteUnverified: 'Strong match, taste-unverified',
};

export interface EvidenceLimitationProps {
  kind: EvidenceLimitationKind;
}

export function EvidenceLimitation({ kind }: EvidenceLimitationProps) {
  return (
    <View style={styles.container} accessibilityLabel={copy[kind]}>
      <CraveText role="caption" tone="secondary">{copy[kind]}</CraveText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignSelf: 'flex-start',
    borderRadius: uiRadius.control,
    borderWidth: 1,
    borderColor: uiColors.border.subtle,
    backgroundColor: uiColors.surface.elevated,
    paddingHorizontal: uiSpace.sm,
    paddingVertical: uiSpace.xs,
  },
});
