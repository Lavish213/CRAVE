// app/(tabs)/hitlist.tsx
import React, { useEffect, useState } from 'react';
import {
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useHitlistStore } from '../../src/stores/hitlistStore';
import { useToast } from '../../src/hooks/useToast';
import { Colors, Spacing, Radius } from '../../src/constants/colors';
import { PlaceCardCompact } from '../../src/components/PlaceCardCompact';
import { EmptyState } from '../../src/components/EmptyState';
import { getCraveItems, CraveItem } from '../../src/api/crave';
import { useAuthStore } from '../../src/stores/authStore';
import { AuthSheet } from '../../src/components/AuthSheet';

export default function HitlistScreen() {
  const router = useRouter();
  const { saves, removeSave } = useHitlistStore();
  const toast = useToast((s) => s.show);
  const user = useAuthStore((s) => s.user);
  const [craves, setCraves] = useState<CraveItem[]>([]);
  const [cravesLoading, setCravesLoading] = useState(true);
  const [authVisible, setAuthVisible] = useState(false);

  useEffect(() => {
    getCraveItems()
      .then(setCraves)
      .catch(() => {})
      .finally(() => setCravesLoading(false));
  }, []);

  // Not signed in — show auth prompt
  if (!user) {
    return (
      <>
        <EmptyState
          icon="person-circle-outline"
          title="Sign in to save places"
          body="Create a free account to build your Hitlist and track Craves."
          ctaLabel="Sign in"
          onCta={() => setAuthVisible(true)}
        />
        <AuthSheet visible={authVisible} onClose={() => setAuthVisible(false)} reason="hitlist" />
      </>
    );
  }

  if (saves.length === 0 && craves.length === 0 && !cravesLoading) {
    return (
      <EmptyState
        icon="bookmark-outline"
        title="Start your food memory"
        body="Save places you want to visit. They live here, waiting for you."
      />
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={saves}
        keyExtractor={(p) => p.id}
        renderItem={({ item }) => (
          <PlaceCardCompact
            place={item}
            onPress={() => router.push(`/place/${item.id}`)}
            rightAction={
              <TouchableOpacity
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                  removeSave(item.id);
                  toast('Removed from Saves');
                }}
                style={styles.removeBtn}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                accessibilityLabel={`Remove ${item.name} from saves`}
                accessibilityRole="button"
              >
                <Ionicons name="close" size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            }
          />
        )}
        contentContainerStyle={styles.list}
        ListHeaderComponent={
          saves.length > 0 ? (
            <View style={styles.screenHeader}>
              <Text style={styles.screenTitle}>Saves</Text>
              <View style={styles.countBadge}>
                <Text style={styles.countBadgeText}>{saves.length}</Text>
              </View>
            </View>
          ) : null
        }
        ListFooterComponent={
          craves.length > 0 ? (
            <View style={styles.cravesSection}>
              <View style={styles.cravesHeader}>
                <Text style={styles.cravesTitle}>Craves</Text>
                <Text style={styles.cravesSub}>Places you've craved, tracked by CRAVE</Text>
              </View>
              {craves.map((item) => (
                <View key={item.id} style={styles.craveRow}>
                  <View style={styles.craveMeta}>
                    <Text style={styles.craveName} numberOfLines={1}>
                      {item.parsed_place_name ?? item.url}
                    </Text>
                    <Text style={item.matched_place_id ? styles.craveStatusMatched : styles.craveStatusPending}>
                      {item.matched_place_id ? '● Matched' : 'Searching…'}
                    </Text>
                  </View>
                  {item.matched_place_id && (
                    <TouchableOpacity
                      style={styles.craveOpenBtn}
                      onPress={() => router.push(`/place/${item.matched_place_id!}`)}
                      accessibilityRole="button"
                      accessibilityLabel={`Open matched place for ${item.parsed_place_name ?? 'this place'}`}
                    >
                      <Text style={styles.craveViewBtn}>View →</Text>
                    </TouchableOpacity>
                  )}
                </View>
              ))}
            </View>
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  list: { padding: Spacing.md, gap: Spacing.sm, paddingBottom: Spacing.xxl },
  screenHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingBottom: Spacing.md,
  },
  screenTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: Colors.text,
  },
  countBadge: {
    backgroundColor: Colors.primary,
    borderRadius: Radius.full,
    minWidth: 22,
    height: 22,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.xs,
  },
  countBadgeText: {
    color: Colors.text,
    fontSize: 11,
    fontWeight: '800',
  },
  removeBtn: {
    padding: Spacing.sm,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cravesSection: { paddingTop: Spacing.lg, paddingBottom: Spacing.sm },
  cravesHeader: {
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  cravesTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: Colors.text,
  },
  cravesSub: {
    fontSize: 12,
    color: Colors.textMuted,
    marginTop: Spacing.xs,
  },
  craveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.sm,
  },
  craveMeta: { flex: 1 },
  craveName: { color: Colors.text, fontSize: 14, fontWeight: '600' },
  craveStatusMatched: { fontSize: 12, marginTop: 2, color: Colors.success },
  craveStatusPending: { fontSize: 12, marginTop: 2, color: Colors.textMuted },
  craveOpenBtn: {
    padding: 8,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  craveViewBtn: {
    color: Colors.primary,
    fontSize: 13,
    fontWeight: '700',
  },
});
