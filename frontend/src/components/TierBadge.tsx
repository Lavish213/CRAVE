// src/components/TierBadge.tsx
import React from 'react';
import { StyleSheet, Text, View, ViewStyle } from 'react-native';
import { Tier } from '../utils/scoring';
import { Radius } from '../constants/colors';

interface Props {
  tier: Tier;
  style?: ViewStyle;
}

export function TierBadge({ tier, style }: Props) {
  return (
    <View style={[styles.badge, { backgroundColor: tier.color + 'DD' }, style]}>
      <Text style={styles.label}>{tier.label.toUpperCase()}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: Radius.sm,
    alignSelf: 'flex-start',
  },
  label: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
});
