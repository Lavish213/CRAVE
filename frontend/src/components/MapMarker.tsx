// src/components/MapMarker.tsx
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Colors } from '../constants/colors';

interface Props {
  color: string;
  size?: number;
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
    backgroundColor: Colors.primary,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.9)',
  },
  count: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
});

export function MapMarkerDot({ color, size = 14 }: Props) {
  return (
    <View style={[
      styles.outer,
      {
        borderColor: color,
        width: size + 8,
        height: size + 8,
        borderRadius: (size + 8) / 2,
      },
    ]}>
      <View style={[
        styles.inner,
        {
          backgroundColor: color,
          width: size,
          height: size,
          borderRadius: size / 2,
        },
      ]} />
    </View>
  );
}

const styles = StyleSheet.create({
  outer: {
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.3)',
  },
  inner: {},
});
