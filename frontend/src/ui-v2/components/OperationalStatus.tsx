import React from 'react';
import { StyleSheet, View } from 'react-native';
import { uiColors, uiRadius, uiSpace } from '../tokens';
import { CraveText } from '../primitives';

export type OperationalState = 'open' | 'closed' | 'stale' | 'unknown';

export interface OperationalStatusProps {
  state: OperationalState;
  detail?: string | null;
  compact?: boolean;
}

const copy: Record<OperationalState, string> = {
  open: 'Open now',
  closed: 'Closed',
  stale: 'Hours not recently verified',
  unknown: 'Hours unavailable',
};

export function OperationalStatus({ state, detail, compact = false }: OperationalStatusProps) {
  const status = state === 'open'
    ? uiColors.status.positive
    : state === 'closed'
      ? uiColors.status.destructive
      : state === 'stale'
        ? uiColors.status.uncertain
        : uiColors.status.neutral;

  return (
    <View style={[styles.container, { backgroundColor: status.background, borderColor: status.border }]} accessibilityLabel={`${copy[state]}${detail ? `, ${detail}` : ''}`}>
      <View style={[styles.dot, { backgroundColor: status.foreground }]} />
      <CraveText role={compact ? 'micro' : 'caption'} style={{ color: status.foreground }}>
        {copy[state]}{detail ? ` · ${detail}` : ''}
      </CraveText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: uiSpace.xs,
    borderWidth: 1,
    borderRadius: uiRadius.pill,
    paddingHorizontal: uiSpace.sm,
    minHeight: 28,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: uiRadius.pill,
  },
});
