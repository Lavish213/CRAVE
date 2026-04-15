// src/components/SectionHeader.tsx
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Colors, Spacing } from '../constants/colors';

interface Props {
  label: string;
  subtext: string;
  count: number;
}

export function SectionHeader({ label, subtext, count }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.accentRow}>
        <View style={styles.accentBar} />
        <View style={styles.top}>
          <Text style={styles.label}>{label}</Text>
          <Text style={styles.count}>{count}</Text>
        </View>
      </View>
      <Text style={styles.subtext}>{subtext}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingTop: Spacing.xl, paddingBottom: Spacing.sm, paddingHorizontal: Spacing.xs },
  accentRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.xs },
  accentBar: {
    width: 2,
    height: 18,
    borderRadius: 1,
    backgroundColor: Colors.primary,
  },
  top: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, flex: 1 },
  label: { fontSize: 18, fontWeight: '800', color: Colors.text, letterSpacing: 0.3, flex: 1 },
  count: { fontSize: 13, color: Colors.textMuted, fontWeight: '500' },
  subtext: { fontSize: 12, color: Colors.textMuted, fontWeight: '400', paddingLeft: Spacing.sm },
});
