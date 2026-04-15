// src/components/TierBadge.tsx
import React, { useMemo } from 'react';
import { StyleSheet, Text, View, ViewStyle } from 'react-native';
import { Tier } from '../utils/scoring';
import { Colors, Radius } from '../constants/colors';

interface Props {
  tier: Tier;
  style?: ViewStyle;
}

export function TierBadge({ tier, style }: Props) {
  const badgeStyle = useMemo(() => [styles.badge, { backgroundColor: tier.color + '33' }], [tier.color]);

  return (
    <View style={[...badgeStyle, style]}>
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
    color: Colors.text,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
});
