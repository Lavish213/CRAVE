// app/taste-profile/[userId].tsx
//
// Private owner view. This screen shows factual ranking aggregates only;
// inferred traits remain "still learning" until Gate 2 provides confidence,
// provenance, and correction support.
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
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  // Distinct from notFound -- a network failure/timeout/5xx on the
  // profile fetch previously collapsed into the same "Profile not found"
  // EmptyState as a genuine 404, with no retry affordance. Same fix as
  // user/[id].tsx's identical profileError.
  const [profileError, setProfileError] = useState(false);
  // Distinct from "no taste profile yet" -- a failed fetchTasteProfile
  // call (network error, 5xx) previously left `taste` at null with
  // nothing to tell it apart from a real empty profile, so it rendered
  // the same "hasn't ranked anything yet" copy with no way to retry.
  const [tasteError, setTasteError] = useState(false);

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
    if (!viewerId || viewerId !== userId) {
      loadedForIdRef.current = userId;
      loadedForViewerRef.current = viewerId;
      setLoading(false);
      return;
    }
    if (loadedForIdRef.current !== userId || loadedForViewerRef.current !== viewerId) {
      // Identity-scoped: only wipe another identity's stale data, so a
      // same-identity refocus/retry doesn't flash the skeleton over
      // still-good data while it quietly re-fetches in the background.
      setProfile(null);
      setTaste(null);
      setLoading(true);
    }
    // Outcome flags describe *this* attempt, not the identity pairing --
    // they must reset on every attempt, including a same-identity retry
    // from ErrorState's onRetry (accessError) or a plain refocus after a
    // transient 404. Previously gated inside the block above: a retry
    // that actually succeeded still rendered the stale error screen over
    // the freshly-fetched, perfectly good data, since nothing ever
    // cleared the flag for a same-identity attempt (confirmed by
    // CodeRabbit; the identity-gated `!profile` catch-all doesn't save
    // this, since profile/taste's own reset is correctly identity-gated).
    setNotFound(false);
    setProfileError(false);
    setTasteError(false);
    // Marked as "attempted" here, before the fetch settles either way --
    // same reasoning as user/[id].tsx's identical comment: the render-time
    // stale-gate below only needs to force the skeleton until an attempt
    // has been made for this identity pairing, not until one has
    // succeeded. Setting this only on success would leave the gate stuck
    // on the skeleton forever after any error.
    loadedForIdRef.current = userId;
    loadedForViewerRef.current = viewerId;
    try {
      // Only fetchProfile is left to reject into the outer catch below --
      // fetchBlockStatus already resolves to null on failure so its own
      // outcome is checked explicitly instead, same as user/[id].tsx.
      const p = await fetchProfile(userId);
      if (myGeneration !== loadGenerationRef.current) return;
      setProfile(p);
      const taste = await fetchTasteProfile(userId).catch(() => null);
      if (myGeneration !== loadGenerationRef.current) return;
      if (taste === null) {
        setTasteError(true);
      } else {
        setTaste(taste);
      }
    } catch (err: any) {
      if (myGeneration !== loadGenerationRef.current) return;
      // A 404 here is real product truth (this account doesn't exist, or
      // its list is private -- see get_public_profile's own is_public
      // gate). Anything else is an infrastructure failure and must stay
      // retryable, same distinction user/[id].tsx already makes.
      if (err?.response?.status === 404) setNotFound(true);
      else setProfileError(true);
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

  if (!me || !isSelf) {
    return (
      <EmptyState
        icon="lock-closed-outline"
        title="Taste Profile is private"
        body="Taste insights are only visible to their owner unless they explicitly share them."
      />
    );
  }

  if (notFound) {
    return (
      <EmptyState
        icon="person-outline"
        title="Profile not found"
        body="This account doesn't exist, or its list is private."
      />
    );
  }

  // profileError (an explicit non-404 failure) and the !profile fallback
  // (shouldn't happen given the two states above, but a defensive
  // catch-all) get the same retryable treatment -- neither is the "not
  // found" product truth above.
  if (profileError || !profile) {
    return <ErrorState message="Couldn't load this profile" onRetry={load} />;
  }

  if (tasteError) {
    return <ErrorState message="Couldn't load taste profile" onRetry={load} />;
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
        <View style={styles.heroTile}>
          <Text style={styles.learningValue}>Still learning</Text>
          <Text style={styles.heroLabel}>inferred taste</Text>
        </View>
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
  learningValue: { color: Colors.text, fontSize: 17, fontWeight: '800' },
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
