// app/taste-profile/[userId].tsx
//
// "Taste Profile" — the equivalent of Beli's own stats screen, confirmed
// via research (cross-referenced across independent sources) to show:
// total restaurants ranked, favorite cuisines, top/highest-ranked city,
// and a percentile rank among other diners. CRAVE already had all of
// this data (PlaceRanking + categories) but never surfaced it as its own
// screen. Deliberately excludes Beli's "Match Score" (taste
// compatibility with a specific friend) — that's being folded into the
// personalized-recommendations feature instead, which needs the same
// user-similarity computation, so it isn't duplicated here.
//
// Viewable on your own profile and on a friend's (same visibility rule
// as the public profile itself — see the backend route's docstring) —
// block enforcement is client-side here, same convention user/[id].tsx
// already uses.
import React, { useCallback, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useLocalSearchParams } from 'expo-router';

import { Colors, Radius, Spacing } from '../../src/constants/colors';
import { EmptyState } from '../../src/components/EmptyState';
import {
  Profile,
  TasteProfile,
  fetchBlockStatus,
  fetchProfile,
  fetchTasteProfile,
} from '../../src/api/social';
import { useAuthStore } from '../../src/stores/authStore';
import { TIER_LABELS, tierColor } from '../../src/utils/rankScore';

export default function TasteProfileScreen() {
  const { userId } = useLocalSearchParams<{ userId: string }>();
  const me = useAuthStore((s) => s.user);
  const isSelf = !!me && me.id === userId;

  const [profile, setProfile] = useState<Profile | null>(null);
  const [taste, setTaste] = useState<TasteProfile | null>(null);
  const [blocked, setBlocked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setNotFound(false);
    try {
      const [p, blockStatus] = await Promise.all([
        fetchProfile(userId),
        isSelf ? Promise.resolve({ blocked: false }) : fetchBlockStatus(userId).catch(() => ({ blocked: false })),
      ]);
      setProfile(p);
      setBlocked(blockStatus.blocked);
      if (!blockStatus.blocked) {
        setTaste(await fetchTasteProfile(userId));
      }
    } catch (err: any) {
      if (err?.response?.status === 404) setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [userId, isSelf]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={Colors.primary} size="large" />
      </View>
    );
  }

  if (notFound || !profile) {
    return (
      <EmptyState
        icon="person-outline"
        title="Profile not found"
        body="This account doesn't exist, or its list is private."
      />
    );
  }

  if (blocked) {
    return (
      <EmptyState
        icon="ban-outline"
        title="Not available"
        body={`You've blocked @${profile.username}.`}
      />
    );
  }

  if (!taste || taste.total_ranked === 0) {
    return (
      <EmptyState
        icon="restaurant-outline"
        title="No taste profile yet"
        body={
          isSelf
            ? "Rank a few places you've eaten and your taste profile will build up here."
            : `@${profile.username} hasn't ranked anything yet.`
        }
      />
    );
  }

  const displayName = profile.display_name ?? profile.username;
  const tierEntries: Array<{ key: keyof TasteProfile['tier_counts']; count: number }> = [
    { key: 'liked', count: taste.tier_counts.liked },
    { key: 'fine', count: taste.tier_counts.fine },
    { key: 'disliked', count: taste.tier_counts.disliked },
  ];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>
        {isSelf ? 'Your Taste Profile' : `${displayName}'s Taste Profile`}
      </Text>

      <View style={styles.heroRow}>
        <View style={styles.heroTile}>
          <Text style={styles.heroValue}>{taste.total_ranked}</Text>
          <Text style={styles.heroLabel}>ranked</Text>
        </View>
        {taste.percentile !== null && (
          <View style={styles.heroTile}>
            {/* percentile = "% of other users you've out-ranked" (higher is
                better) -- displayed as the more intuitive "top X%" framing,
                floored at 1 so a top performer never reads as "Top 0%". */}
            <Text style={styles.heroValue}>Top {Math.max(1, 100 - taste.percentile)}%</Text>
            <Text style={styles.heroLabel}>of all diners</Text>
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionLabel}>BREAKDOWN</Text>
        <View style={styles.tierRow}>
          {tierEntries.map(({ key, count }) => (
            <View key={key} style={styles.tierTile}>
              <Text style={[styles.tierCount, { color: tierColor(key) }]}>{count}</Text>
              <Text style={styles.tierLabel}>{TIER_LABELS[key]}</Text>
            </View>
          ))}
        </View>
      </View>

      {taste.favorite_cuisine && (
        <View style={styles.card}>
          <Ionicons name="restaurant-outline" size={20} color={Colors.primary} />
          <View style={styles.cardMeta}>
            <Text style={styles.cardLabel}>Favorite cuisine</Text>
            <Text style={styles.cardValue}>{taste.favorite_cuisine}</Text>
          </View>
        </View>
      )}

      {taste.top_city && (
        <View style={styles.card}>
          <Ionicons name="location-outline" size={20} color={Colors.primary} />
          <View style={styles.cardMeta}>
            <Text style={styles.cardLabel}>Top city</Text>
            <Text style={styles.cardValue}>
              {taste.top_city.name} · {taste.top_city.count} ranked
            </Text>
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.lg, paddingBottom: Spacing.xxl, gap: Spacing.lg },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.background,
  },
  title: { color: Colors.text, fontSize: 22, fontWeight: '800' },
  heroRow: { flexDirection: 'row', gap: Spacing.sm },
  heroTile: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: Spacing.lg,
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  heroValue: { color: Colors.text, fontSize: 24, fontWeight: '800' },
  heroLabel: { color: Colors.textMuted, fontSize: 12, marginTop: 2, fontWeight: '600' },
  section: { gap: Spacing.sm },
  sectionLabel: {
    color: Colors.primary,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.2,
  },
  tierRow: { flexDirection: 'row', gap: Spacing.sm },
  tierTile: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  tierCount: { fontSize: 20, fontWeight: '800' },
  tierLabel: { color: Colors.textMuted, fontSize: 11, marginTop: 2, fontWeight: '600' },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    padding: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  cardMeta: { flex: 1 },
  cardLabel: { color: Colors.textMuted, fontSize: 12, fontWeight: '600' },
  cardValue: { color: Colors.text, fontSize: 16, fontWeight: '700', marginTop: 2 },
});
