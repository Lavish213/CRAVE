import React from 'react';
import { StyleSheet, View } from 'react-native';
import { uiColors, uiElevation, uiRadius, uiSpace } from '../tokens';
import { CraveText } from '../primitives';

export interface CraveMapPinProps {
  label?: string;
  selected?: boolean;
  closed?: boolean;
  clusterCount?: number;
}

export function CraveMapPin({ label, selected = false, closed = false, clusterCount }: CraveMapPinProps) {
  const isCluster = typeof clusterCount === 'number' && clusterCount > 1;
  const borderColor = closed ? uiColors.border.destructive : selected ? uiColors.border.selected : uiColors.border.strong;
  const backgroundColor = closed
    ? uiColors.status.destructive.background
    : selected
      ? uiColors.surface.selected
      : uiColors.surface.overlay;

  return (
    <View
      style={[
        styles.pin,
        selected ? styles.selected : null,
        isCluster ? styles.cluster : null,
        { borderColor, backgroundColor },
      ]}
      accessible
      accessibilityLabel={isCluster ? `${clusterCount} places` : `${label ?? 'Place'}${closed ? ', closed' : ''}${selected ? ', selected' : ''}`}
    >
      {isCluster ? (
        <CraveText role="caption" tone={selected ? 'brand' : 'primary'}>{clusterCount}</CraveText>
      ) : (
        <>
          <View style={[styles.core, { backgroundColor: closed ? uiColors.status.destructive.foreground : uiColors.accent.brand }]} />
          {selected && label ? <CraveText role="micro" numberOfLines={1}>{label}</CraveText> : null}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  pin: {
    minWidth: 28,
    minHeight: 28,
    borderWidth: 2,
    borderRadius: uiRadius.pill,
    paddingHorizontal: uiSpace.xs,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: uiSpace.xs,
    ...uiElevation.control,
  },
  selected: {
    minHeight: 36,
    borderWidth: 3,
    paddingHorizontal: uiSpace.sm,
  },
  cluster: {
    minWidth: 36,
    minHeight: 36,
  },
  core: {
    width: 10,
    height: 10,
    borderRadius: uiRadius.pill,
  },
});
