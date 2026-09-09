import React from 'react';
import { StyleSheet, View } from 'react-native';
import { uiSpace } from '../tokens';
import { CraveText } from '../primitives';

export type ReasonKind = 'bestMatch' | 'saferPick' | 'worthExploring' | 'bestFit' | 'safeBet' | 'wildcard' | 'generic';

const labels: Record<ReasonKind, string | null> = {
  bestMatch: 'BEST MATCH FOR YOU',
  saferPick: 'SAFER PICK',
  worthExploring: 'WORTH EXPLORING',
  bestFit: 'BEST FIT TONIGHT',
  safeBet: 'SAFE BET',
  wildcard: 'WILDCARD',
  generic: null,
};

export interface ReasonLineProps {
  kind?: ReasonKind;
  reason?: string | null;
  compact?: boolean;
}

export function ReasonLine({ kind = 'generic', reason, compact = false }: ReasonLineProps) {
  const label = labels[kind];
  if (!label && !reason) return null;

  return (
    <View style={styles.container}>
      {label ? <CraveText role="micro" tone="brand">{label}</CraveText> : null}
      {reason ? <CraveText role={compact ? 'caption' : 'body'}>{reason}</CraveText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: uiSpace.xs,
  },
});
