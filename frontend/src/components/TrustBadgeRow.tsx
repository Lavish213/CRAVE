// src/components/TrustBadgeRow.tsx
import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { TrustBadge } from '../utils/scoring';

interface Props {
  badges: TrustBadge[];
}

export function TrustBadgeRow({ badges }: Props) {
  if (badges.length === 0) return null;
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.scroll}
    >
      {badges.map((b, i) => (
        <View key={i} style={[styles.badge, { backgroundColor: b.bg }]}>
          <Text style={[styles.label, { color: b.color }]}>{b.label}</Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingHorizontal: 16, gap: 8, paddingVertical: 4 },
  badge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    minHeight: 32,
    justifyContent: 'center',
  },
  label: { fontSize: 12, fontWeight: '700', letterSpacing: 0.3 },
});
