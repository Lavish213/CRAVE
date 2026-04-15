// src/components/TrendingStrip.tsx
import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { PlaceOut } from '../api/places';
import { getTier } from '../utils/scoring';
import { Colors } from '../constants/colors';

interface Props {
  places: PlaceOut[];
  onPress: (id: string) => void;
}

export function TrendingStrip({ places, onPress }: Props) {
  if (places.length === 0) return null;
  return (
    <View style={styles.container}>
      <Text style={styles.heading}>TRENDING</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {places.map((p) => {
          const tier = getTier(p.rank_score);
          return (
            <TouchableOpacity
              key={p.id}
              style={styles.chip}
              onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); onPress(p.id); }}
              activeOpacity={0.8}
              accessibilityLabel={`${p.name}, trending`}
              accessibilityRole="button"
            >
              <View style={[styles.dot, { backgroundColor: tier.color }]} />
              <Text style={styles.chipText} numberOfLines={1}>{p.name}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 4 },
  heading: {
    fontSize: 10,
    fontWeight: '800',
    color: Colors.textMuted,
    letterSpacing: 1.5,
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 4,
  },
  scroll: { paddingHorizontal: 12, gap: 8, paddingBottom: 4 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Colors.surface,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: Colors.border,
    minHeight: 36,
  },
  dot: { width: 7, height: 7, borderRadius: 4 },
  chipText: { color: Colors.text, fontSize: 13, fontWeight: '500', maxWidth: 130 },
});
