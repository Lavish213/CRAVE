// src/components/MapMarker.tsx
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Colors } from '../constants/colors';

interface Props {
  color: string;
  size?: number;
  selected?: boolean;
}

interface ClusterProps {
  count: number;
}

export function MapClusterDot({ count }: ClusterProps) {
  // Scale up slightly for larger clusters so dense areas read as "bigger",
  // capped so it never overwhelms the map.
  const size = Math.min(52, 32 + Math.log2(count) * 4);

  return (
    <View
      style={[
        clusterStyles.outer,
        { width: size, height: size, borderRadius: size / 2 },
      ]}
    >
      <Text style={clusterStyles.count}>{count > 99 ? '99+' : count}</Text>
    </View>
  );
}

const clusterStyles = StyleSheet.create({
  outer: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.mapCluster,
    borderWidth: 2,
    borderColor: Colors.onMedia,
  },
  count: {
    color: Colors.onPrimary,
    fontWeight: '700',
    fontSize: 13,
  },
});

export function MapMarkerDot({ color, size = 14, selected = false }: Props) {
  const outerSize = selected ? size + 18 : size + 8;
  const innerSize = selected ? size + 4 : size;

  return (
    <View style={[
      styles.outer,
      selected && styles.outerSelected,
      {
        borderColor: selected ? Colors.mapSelected : color,
        width: outerSize,
        height: outerSize,
        borderRadius: outerSize / 2,
      },
    ]}>
      <View style={[
        styles.inner,
        {
          backgroundColor: selected ? Colors.mapSelected : color,
          width: innerSize,
          height: innerSize,
          borderRadius: innerSize / 2,
        },
      ]} />
      {selected ? <View style={styles.selectedStem} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  outer: {
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.overlayDim,
  },
  outerSelected: {
    borderWidth: 3,
    backgroundColor: Colors.surface,
  },
  inner: {},
  selectedStem: {
    position: 'absolute',
    bottom: -6,
    width: 3,
    height: 8,
    borderRadius: 2,
    backgroundColor: Colors.mapSelected,
  },
});
