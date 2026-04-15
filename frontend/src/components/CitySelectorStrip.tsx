// src/components/CitySelectorStrip.tsx
import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity } from 'react-native';
import * as Haptics from 'expo-haptics';
import { useCityStore } from '../stores/cityStore';
import { Colors } from '../constants/colors';

export function CitySelectorStrip() {
  const cities = useCityStore((s) => s.cities);
  const selectedCity = useCityStore((s) => s.selectedCity);
  const selectCity = useCityStore((s) => s.selectCity);

  if (cities.length === 0) return null;

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={styles.strip}
      contentContainerStyle={styles.content}
    >
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
  content: { paddingHorizontal: 12, paddingVertical: 8, gap: 8 },
  pill: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
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
