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
import React, { useCallback, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useLocalSearchParams } from 'expo-router';

import { Colors, Radius, Spacing } from '../../src/constants/colors';
import { EmptyState } from '../../src/components/EmptyState';
import { ErrorState } from '../../src/components/ErrorState';
import { SkeletonRowList } from '../../src/components/SkeletonCard';
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
  const [accessError, setAccessError] = useState(false);

  // expo-router can reuse this screen instance across a param change (e.g.
  // tapping from one person's taste profile into another's) -- without a
  // guard, a slow response for the *previous* userId could resolve after
  // the new one's and silently repaint this screen with the wrong person's
  // stats.
  const loadGenerationRef = useRef(0);
  // Whose data this screen currently holds -- both the profile being
  // viewed AND who was viewing it, same pattern as user/[id].tsx's
  // identical guard (see its own comment for the full rationale: blocked/
  // taste are relative to the viewer, not just the profile being viewed,
  // so a viewer switch with the same target userId -- isSelf unchanged in
  // both cases -- must still force a fresh load).
  //
  // Also closes a real confirmed bug: previously neither `taste` nor
  // `blocked` were ever reset when a new load started, only overwritten on
  // success. Profile A's taste profile loads and renders; navigating to
  // profile B succeeds on the profile fetch (so the header correctly shows
  // B) but then B's *taste* fetch itself fails (network error, 5xx) --
  // the catch block only ever sets `notFound` for a 404, so `taste` was
  // simply left holding A's stale data, which then rendered in full under
  // B's identity. Resetting profile/taste/blocked whenever the identity
  // pairing changes (not on every load -- a same-identity refocus
  // shouldn't flash the skeleton) closes this.
  const loadedForIdRef = useRef<string | null>(null);
  const loadedForViewerRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    if (!userId) return;
    const myGeneration = ++loadGenerationRef.current;
    const viewerId = me?.id ?? null;
    if (loadedForIdRef.current !== userId || loadedForViewerRef.current !== viewerId) {
      setProfile(null);
      setTaste(null);
      setBlocked(false);
      setNotFound(false);
      setAccessError(false);
      setLoading(true);
    }
    // Marked as "attempted" here, before the fetch settles either way --
    // same reasoning as user/[id].tsx's identical comment: the render-time
    // stale-gate below only needs to force the skeleton until an attempt
    // has been made for this identity pairing, not until one has
    // succeeded. Setting this only on success would leave the gate stuck
    // on the skeleton forever after any error.
    loadedForIdRef.current = userId;
    loadedForViewerRef.current = viewerId;
    try {
      const [p, blockStatus] = await Promise.all([
        fetchProfile(userId),
        isSelf ? Promise.resolve({ blocked: false }) : fetchBlockStatus(userId).catch(() => null),
      ]);
      if (myGeneration !== loadGenerationRef.current) return;
      setProfile(p);
      if (blockStatus === null) {
        setAccessError(true);
        return;
      }
      setBlocked(blockStatus.blocked);
      if (!blockStatus.blocked) {
        const taste = await fetchTasteProfile(userId);
        if (myGeneration !== loadGenerationRef.current) return;
        setTaste(taste);
      }
    } catch (err: any) {
      if (myGeneration !== loadGenerationRef.current) return;
      if (err?.response?.status === 404) setNotFound(true);
    } finally {
      if (myGeneration === loadGenerationRef.current) setLoading(false);
    }
  }, [userId, isSelf, me?.id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  // Derived at render time, not just from `loading` -- `loading` only
  // flips back to true from inside load(), which runs in an *effect*
  // (useFocusEffect), one render after `userId`/`me` themselves have
  // already changed. Gating on the refs directly closes that one-render
  // gap, same fix as user/[id].tsx's identical `isStaleForCurrentIdentity`.
  const isStaleForCurrentIdentity =
    loadedForIdRef.current !== userId || loadedForViewerRef.current !== (me?.id ?? null);
  if (loading || isStaleForCurrentIdentity) {
    // Same treatment as app/(tabs)/profile.tsx's own stats+ranked-list
    // loading state -- this screen was still a plain ActivityIndicator,
    // inconsistent with every other list/stat-shaped screen in the app.
    return (
      <View style={styles.content}>
        <SkeletonRowList count={4} />
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

  if (accessError) {
    return <ErrorState message="Couldn't verify profile access" onRetry={load} />;
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
        {!isSelf && taste.match_score !== null && (
          <View style={styles.heroTile}>
            <Text style={[styles.heroValue, { color: Colors.primary }]}>
              {taste.match_score}%
            </Text>
            <Text style={styles.heroLabel}>taste match</Text>
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
  heroLabel: { color: Colors.textSecondary, fontSize: 12, marginTop: 2, fontWeight: '600' },
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
  tierLabel: { color: Colors.textSecondary, fontSize: 11, marginTop: 2, fontWeight: '600' },
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
  cardLabel: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600' },
  cardValue: { color: Colors.text, fontSize: 16, fontWeight: '700', marginTop: 2 },
});
