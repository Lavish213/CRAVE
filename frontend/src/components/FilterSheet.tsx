// src/components/FilterSheet.tsx
import React, { useMemo } from 'react';
import {
  Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { Colors, Spacing, Radius } from '../constants/colors';
import { useCategoryTypes } from '../hooks/useCategoryTypes';

// Truly meaningless as a filter chip regardless of type -- not what E8
// is about (that's a real taxonomy question), just genuinely empty
// signal. "Restaurant"/"Bar"/"Fast Casual" describe almost every place
// in the catalog and would match everything, same reasoning the
// backend's own _VOID_CATEGORIES/_GENERIC_CATEGORIES apply to `other`.
const VOID_FILTER_CATS = new Set(['restaurant', 'restaurants', 'bar', 'bars', 'other', 'others', 'fast casual', '']);

// Display order + label for each type section. `null`/unrecognized types
// (a category the frontend's cache hasn't caught up on, or a genuine
// lookup miss) fall into a final untitled bucket rather than being
// silently dropped -- see _sectionFor below.
const TYPE_SECTIONS: Array<{ type: string; label: string }> = [
  { type: 'cuisine', label: 'CUISINE' },
  { type: 'venue', label: 'VENUE' },
  { type: 'dietary', label: 'DIETARY' },
  // Factual header, not "Values" -- these three are business-ownership
  // attributes, not this filter's place to editorialize on. See
  // docs/CATEGORY_TAXONOMY_DESIGN_2026-08-31.md's "Needs a human call"
  // section for the fuller reasoning.
  { type: 'ownership', label: 'OWNERSHIP' },
  { type: 'occasion', label: 'OCCASION' },
  { type: 'recognition', label: 'RECOGNITION' },
];

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
  // Name -> type lookup, fetched once and cached module-wide across every
  // FilterSheet instance (Feed, Search, Map each render their own). This
  // is purely for classification; *which* chips actually render still
  // comes from availableCategories below (city/load-scoped -- see its own
  // comment at each call site for why a global category list was
  // deliberately rejected as the source of chips themselves).
  const typeByName = useCategoryTypes();

  // Groups availableCategories (already city/load-scoped) by type,
  // preserving TYPE_SECTIONS's display order. A name with no match in
  // typeByName (cache not yet loaded, or a genuine lookup miss) lands in
  // the untitled fallback bucket rather than vanishing -- every real
  // category the caller passed in still shows up somewhere.
  const sections = useMemo(() => {
    const visible = availableCategories.filter((c) => !VOID_FILTER_CATS.has(c.toLowerCase()));
    const byType = new Map<string, string[]>();
    const unclassified: string[] = [];
    for (const cat of visible) {
      const type = typeByName.get(cat.toLowerCase());
      if (!type) {
        unclassified.push(cat);
        continue;
      }
      if (!byType.has(type)) byType.set(type, []);
      byType.get(type)!.push(cat);
    }
    const result = TYPE_SECTIONS
      .map(({ type, label }) => ({ label, cats: byType.get(type) ?? [] }))
      .filter((s) => s.cats.length > 0);
    if (unclassified.length > 0) result.push({ label: 'MORE', cats: unclassified });
    return result;
  }, [availableCategories, typeByName]);

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
      {/* Backdrop -- accessible=false so VoiceOver/TalkBack skip straight
          to the labeled "Close filter" button below instead of stopping
          on an invisible, undescribed full-screen element first. */}
      <Pressable style={styles.backdrop} onPress={onClose} accessible={false} />

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

          {/* Categories -- grouped by type (E8) instead of one flat
              "CUISINE" list that used to also silently hide every
              dietary/ownership/occasion/recognition category behind a
              blacklist. See docs/CATEGORY_TAXONOMY_DESIGN_2026-08-31.md,
              Option A. */}
          {sections.map(({ label, cats }) => (
            <React.Fragment key={label}>
              <Text style={[styles.sectionLabel, styles.sectionLabelSpaced]}>{label}</Text>
              <View style={styles.chipRow}>
                {cats.map((cat) => {
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
            </React.Fragment>
          ))}
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
    color: Colors.textSecondary,
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
