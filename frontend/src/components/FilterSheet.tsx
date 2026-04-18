// src/components/FilterSheet.tsx
import React from 'react';
import {
  Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { Colors, Spacing, Radius } from '../constants/colors';

const GENERIC_FILTER_CATS = new Set([
  'restaurant', 'restaurants', 'bar', 'bars',
  'other', 'others', 'fast casual',
  'black owned', 'family owned', 'woman owned',
  'kid friendly', 'gluten free', 'halal',
  'local favorite', 'late night', 'romantic', 'michelin rated',
  '',
]);

export interface FilterState {
  priceTiers: number[]; // empty = all, [1] = $, [1,2] = $ and $$, etc.
  categories: string[]; // empty = all
}

export const EMPTY_FILTERS: FilterState = { priceTiers: [], categories: [] };

export function hasActiveFilters(f: FilterState): boolean {
  return f.priceTiers.length > 0 || f.categories.length > 0;
}

interface Props {
  visible: boolean;
  onClose: () => void;
  filters: FilterState;
  onChange: (f: FilterState) => void;
  availableCategories: string[]; // derived from loaded places
}

const PRICE_OPTIONS = [
  { value: 1, label: '$' },
  { value: 2, label: '$$' },
  { value: 3, label: '$$$' },
];

export function FilterSheet({ visible, onClose, filters, onChange, availableCategories }: Props) {
  const togglePrice = (v: number) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const current = filters.priceTiers;
    onChange({
      ...filters,
      priceTiers: current.includes(v) ? current.filter(x => x !== v) : [...current, v],
    });
  };

  const toggleCategory = (cat: string) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const current = filters.categories;
    onChange({
      ...filters,
      categories: current.includes(cat) ? current.filter(x => x !== cat) : [...current, cat],
    });
  };

  const clearAll = () => {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    onChange(EMPTY_FILTERS);
  };

  const activeCount = filters.priceTiers.length + filters.categories.length;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      {/* Backdrop */}
      <Pressable style={styles.backdrop} onPress={onClose} />

      {/* Sheet */}
      <View style={styles.sheet}>
        {/* Handle */}
        <View style={styles.handle} />

        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Filter</Text>
          <View style={styles.headerRight}>
            {activeCount > 0 && (
              <TouchableOpacity onPress={clearAll} accessibilityRole="button" accessibilityLabel="Clear all filters">
                <Text style={styles.clearBtn}>Clear all</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity onPress={onClose} style={styles.closeBtn} accessibilityRole="button" accessibilityLabel="Close filter">
              <Ionicons name="close" size={20} color={Colors.textSecondary} />
            </TouchableOpacity>
          </View>
        </View>

        <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          {/* Price tier */}
          <Text style={styles.sectionLabel}>PRICE</Text>
          <View style={styles.chipRow}>
            {PRICE_OPTIONS.map(({ value, label }) => {
              const active = filters.priceTiers.includes(value);
              return (
                <TouchableOpacity
                  key={value}
                  style={[styles.chip, active && styles.chipActive]}
                  onPress={() => togglePrice(value)}
                  activeOpacity={0.75}
                  accessibilityRole="button"
                  accessibilityLabel={`Price tier ${label}`}
                >
                  <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* Categories */}
          {availableCategories.length > 0 && (
            <>
              <Text style={[styles.sectionLabel, styles.sectionLabelSpaced]}>CUISINE</Text>
              <View style={styles.chipRow}>
                {availableCategories.filter(c => !GENERIC_FILTER_CATS.has(c.toLowerCase())).map((cat) => {
                  const active = filters.categories.includes(cat);
                  return (
                    <TouchableOpacity
                      key={cat}
                      style={[styles.chip, active && styles.chipActive]}
                      onPress={() => toggleCategory(cat)}
                      activeOpacity={0.75}
                      accessibilityRole="button"
                      accessibilityLabel={cat}
                    >
                      <Text style={[styles.chipText, active && styles.chipTextActive]}>{cat}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </>
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
  },
  sheet: {
    backgroundColor: Colors.surface,
    borderTopLeftRadius: Radius.card,
    borderTopRightRadius: Radius.card,
    borderTopWidth: 1,
    borderColor: Colors.border,
    paddingBottom: Spacing.xxl,
    maxHeight: '75%',
  },
  handle: {
    width: 36,
    height: 4,
    borderRadius: Radius.full,
    backgroundColor: Colors.border,
    alignSelf: 'center',
    marginTop: Spacing.sm,
    marginBottom: Spacing.xs,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderColor: Colors.border,
  },
  title: { fontSize: 17, fontWeight: '700', color: Colors.text },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  clearBtn: { color: Colors.primary, fontSize: 14, fontWeight: '600' },
  closeBtn: { padding: Spacing.xs, minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  scroll: { flexGrow: 0 },
  scrollContent: { padding: Spacing.lg },
  sectionLabel: {
    color: Colors.textMuted,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: Spacing.sm,
  },
  sectionLabelSpaced: {
    marginTop: Spacing.lg,
  },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  chip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.background,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipActive: {
    borderColor: Colors.primary,
    backgroundColor: Colors.primary + '22',
  },
  chipText: { color: Colors.textSecondary, fontSize: 14, fontWeight: '600' },
  chipTextActive: { color: Colors.primary },
});
