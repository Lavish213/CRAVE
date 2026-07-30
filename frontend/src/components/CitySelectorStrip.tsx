// src/components/CitySelectorStrip.tsx
import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity } from 'react-native';
import * as Haptics from 'expo-haptics';
import { useCityStore } from '../stores/cityStore';
import { Colors, Radius, Spacing } from '../constants/colors';

export function CitySelectorStrip() {
  const cities = useCityStore((s) => s.cities);
  const selectedCity = useCityStore((s) => s.selectedCity);
  const selectCity = useCityStore((s) => s.selectCity);
  const clearCity = useCityStore((s) => s.clearCity);

  if (cities.length === 0) return null;

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={styles.strip}
      contentContainerStyle={styles.content}
    >
      <TouchableOpacity
        style={[styles.pill, !selectedCity && styles.pillActive]}
        onPress={() => { Haptics.selectionAsync(); clearCity(); }}
        activeOpacity={0.75}
        hitSlop={{ top: 8, bottom: 8, left: 4, right: 4 }}
        accessibilityLabel="Use my location"
        accessibilityRole="button"
        accessibilityState={{ selected: !selectedCity }}
      >
        <Text style={[styles.pillText, !selectedCity && styles.pillTextActive]}>
          📍 Near Me
        </Text>
      </TouchableOpacity>
      {cities.map((city) => {
        const active = selectedCity?.id === city.id;
        return (
          <TouchableOpacity
            key={city.id}
            style={[styles.pill, active && styles.pillActive]}
            onPress={() => { Haptics.selectionAsync(); selectCity(city); }}
            activeOpacity={0.75}
            hitSlop={{ top: 8, bottom: 8, left: 4, right: 4 }}
            accessibilityLabel={`Select ${city.name}`}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
          >
            <Text style={[styles.pillText, active && styles.pillTextActive]}>
              {city.name}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  strip: { flexGrow: 0 },
  content: { paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm, gap: Spacing.sm },
  pill: {
    paddingHorizontal: 14,
    paddingVertical: Spacing.sm,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    minHeight: 36,
    justifyContent: 'center',
  },
  pillActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  pillText: { color: Colors.textSecondary, fontSize: 13, fontWeight: '500' },
  pillTextActive: { color: Colors.text, fontWeight: '700' },
});
