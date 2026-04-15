// src/components/MapMarker.tsx
import React from 'react';
import { StyleSheet, View } from 'react-native';

interface Props {
  color: string;
  size?: number;
}

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
