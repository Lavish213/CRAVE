// app/(tabs)/profile.tsx
//
// Your identity in the app: who you are, your ranked list, and the two
// social surfaces (friends feed, leaderboard) hanging off it.
//
// Framing follows the Spotify-Wrapped lesson rather than a dashboard one:
// the headline is a statement about the person ("42 places ranked. You
// know this city.") instead of a bare metric, because that's the line
// someone screenshots. Settings live behind the gear here rather than in
// their own tab — the same place every comparable app puts them.
import React, { useCallback, useState } from 'react';
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useRouter } from 'expo-router';

import { Colors, Radius, Spacing } from '../../src/constants/colors';
import { EmptyState } from '../../src/components/EmptyState';
import { AuthSheet } from '../../src/components/AuthSheet';
import { RankedPlaceRow } from '../../src/components/RankedPlaceRow';
import { SkeletonRowList } from '../../src/components/SkeletonCard';
import { useAuthStore } from '../../src/stores/authStore';
import {
  Profile,
  RankedPlace,
  fetchFollowers,
  fetchFollowing,
  fetchMyProfile,
  fetchMyRankings,
} from '../../src/api/social';
import {
  RECOMMENDATION_THRESHOLD,
  rankedListHeadline,
  recommendationProgress,
} from '../../src/utils/rankScore';

function StatTile({ value, label, onPress }: { value: number | string; label: string; onPress?: () => void }) {
  const inner = (
    <View style={styles.statTile}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
  if (!onPress) return inner;
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.75} accessibilityRole="button" accessibilityLabel={`${value} ${label}`} style={{ flex: 1 }}>
      {inner}
    </TouchableOpacity>
  );
}

export default function ProfileScreen() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  const [profile, setProfile] = useState<Profile | null>(null);
  const [rankings, setRankings] = useState<RankedPlace[]>([]);
  const [followingCount, setFollowingCount] = useState(0);
  const [followerCount, setFollowerCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [authVisible, setAuthVisible] = useState(false);

  const load = useCallback(async () => {
    if (!user) {
      setLoading(false);
      return;
    }
    try {
      // Independent reads — one slow/failing call shouldn't blank the
      // whole screen, so they settle individually rather than all-or-nothing.
      const [p, r, following, followers] = await Promise.all([
        fetchMyProfile().catch(() => null),
        fetchMyRankings().catch(() => [] as RankedPlace[]),
        fetchFollowing().catch(() => [] as string[]),
        fetchFollowers().catch(() => [] as string[]),
      ]);
      setProfile(p);
      setRankings(r);
      setFollowingCount(following.length);
      setFollowerCount(followers.length);
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  // Re-read on focus: coming back from the ranking flow should show the
  // place that was just added, not a stale list.
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await load();
    } finally {
      setRefreshing(false);
    }
  };

  if (!user) {
    return (
      <>
        <EmptyState
          icon="person-circle-outline"
          title="Sign in to build your list"
          body="Rank the places you've eaten, follow friends, and see how your taste stacks up."
          ctaLabel="Sign in"
          onCta={() => setAuthVisible(true)}
        />
        <AuthSheet visible={authVisible} onClose={() => setAuthVisible(false)} reason="profile" />
      </>
    );
  }

  if (loading) {
    return (
      <View style={styles.content}>
        <SkeletonRowList count={4} />
      </View>
    );
  }

  // Signed in but never picked a username — everything social keys off it.
  if (!profile) {
    return (
      <EmptyState
        icon="at-outline"
        title="Pick a username"
        body="You need a handle before you can be followed or show up on a leaderboard."
        ctaLabel="Choose username"
        onCta={() => router.push('/profile-setup')}
      />
    );
  }

  const { unlocked, remaining } = recommendationProgress(rankings.length);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={Colors.primary} />
      }
    >
      <View style={styles.header}>
        {profile.avatar_url ? (
          <Image source={profile.avatar_url} style={styles.avatar} contentFit="cover" />
        ) : (
          <View style={[styles.avatar, styles.avatarFallback]}>
            <Text style={styles.avatarInitial}>
              {(profile.display_name ?? profile.username).charAt(0).toUpperCase()}
            </Text>
          </View>
        )}

        <View style={styles.headerMeta}>
          <Text style={styles.displayName} numberOfLines={1}>
            {profile.display_name ?? profile.username}
          </Text>
          <Text style={styles.username}>@{profile.username}</Text>
          {profile.bio ? <Text style={styles.bio} numberOfLines={2}>{profile.bio}</Text> : null}
        </View>

        <TouchableOpacity
          onPress={() => router.push('/settings')}
          style={styles.gearBtn}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          accessibilityRole="button"
          accessibilityLabel="Settings"
        >
          <Ionicons name="settings-outline" size={22} color={Colors.textSecondary} />
        </TouchableOpacity>
      </View>

      <View style={styles.statsRow}>
        <StatTile value={rankings.length} label="ranked" />
        <StatTile value={followerCount} label="followers" />
        <StatTile value={followingCount} label="following" />
      </View>

      <Text style={styles.headline}>{rankedListHeadline(rankings.length)}</Text>

      {!unlocked ? (
        <View style={styles.unlockCard}>
          <Ionicons name="sparkles-outline" size={18} color={Colors.primary} />
          <Text style={styles.unlockText}>
            Rank {remaining} more {remaining === 1 ? 'place' : 'places'} to unlock
            recommendations. Below {RECOMMENDATION_THRESHOLD} there isn't enough
            signal to match you to anyone's taste.
          </Text>
        </View>
      ) : null}

      <View style={styles.linkRow}>
        <TouchableOpacity
          style={styles.linkBtn}
          onPress={() => router.push('/friends-feed')}
          accessibilityRole="button"
          accessibilityLabel="Friends activity"
        >
          <Ionicons name="people-outline" size={18} color={Colors.primary} />
          <Text style={styles.linkBtnText}>Friends</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.linkBtn}
          onPress={() => router.push('/leaderboard')}
          accessibilityRole="button"
          accessibilityLabel="Leaderboard"
        >
          <Ionicons name="trophy-outline" size={18} color={Colors.primary} />
          <Text style={styles.linkBtnText}>Leaderboard</Text>
        </TouchableOpacity>
        {rankings.length > 0 && user && (
          <TouchableOpacity
            style={styles.linkBtn}
            onPress={() => router.push(`/taste-profile/${user.id}`)}
            accessibilityRole="button"
            accessibilityLabel="Your Taste Profile"
          >
            <Ionicons name="restaurant-outline" size={18} color={Colors.primary} />
            <Text style={styles.linkBtnText}>Taste Profile</Text>
          </TouchableOpacity>
        )}
      </View>

      <Text style={styles.sectionTitle}>Your list</Text>

      {rankings.length === 0 ? (
        <View style={styles.emptyList}>
          <Text style={styles.emptyListTitle}>Nothing ranked yet</Text>
          <Text style={styles.emptyListBody}>
            Open any place you've eaten at and tap "I ate here" — you'll compare
            it against your other spots to place it exactly.
          </Text>
          <TouchableOpacity
            style={styles.emptyCta}
            onPress={() => router.push('/')}
            accessibilityRole="button"
            accessibilityLabel="Browse places"
          >
            <Text style={styles.emptyCtaText}>Browse places</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.list}>
          {rankings.map((r, i) => (
            <RankedPlaceRow
              key={r.place_id}
              position={i + 1}
              name={r.name ?? 'Unknown place'}
              imageUrl={r.primary_image_url}
              score={r.rank_score}
              tier={r.tier}
              note={r.note}
              onPress={() => router.push(`/place/${r.place_id}`)}
            />
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.lg, paddingBottom: Spacing.xxl, gap: Spacing.lg },

  header: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  avatar: { width: 64, height: 64, borderRadius: Radius.full, backgroundColor: Colors.surfaceElevated },
  avatarFallback: { alignItems: 'center', justifyContent: 'center' },
  avatarInitial: { color: Colors.text, fontSize: 26, fontWeight: '800' },
  headerMeta: { flex: 1 },
  displayName: { color: Colors.text, fontSize: 20, fontWeight: '800' },
  username: { color: Colors.textMuted, fontSize: 14, marginTop: 1 },
  bio: { color: Colors.textSecondary, fontSize: 13, marginTop: Spacing.xs, lineHeight: 18 },
  gearBtn: { padding: Spacing.sm, minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },

  statsRow: { flexDirection: 'row', gap: Spacing.sm },
  statTile: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingVertical: Spacing.md,
    alignItems: 'center',
  },
  statValue: { color: Colors.text, fontSize: 22, fontWeight: '800' },
  statLabel: { color: Colors.textMuted, fontSize: 12, marginTop: 2 },

  headline: { color: Colors.text, fontSize: 17, fontWeight: '700', lineHeight: 23 },

  unlockCard: {
    flexDirection: 'row',
    gap: Spacing.sm,
    padding: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  unlockText: { flex: 1, color: Colors.textSecondary, fontSize: 13, lineHeight: 19 },

  linkRow: { flexDirection: 'row', gap: Spacing.sm },
  linkBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 12,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    minHeight: 44,
  },
  linkBtnText: { color: Colors.primary, fontSize: 14, fontWeight: '700' },

  sectionTitle: { color: Colors.text, fontSize: 18, fontWeight: '800' },
  list: { gap: Spacing.sm },

  emptyList: {
    padding: Spacing.lg,
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    gap: Spacing.sm,
  },
  emptyListTitle: { color: Colors.text, fontSize: 16, fontWeight: '700' },
  emptyListBody: {
    color: Colors.textSecondary,
    fontSize: 13,
    textAlign: 'center',
    lineHeight: 19,
  },
  emptyCta: {
    marginTop: Spacing.xs,
    paddingHorizontal: Spacing.lg,
    paddingVertical: 10,
    borderRadius: Radius.pill,
    backgroundColor: Colors.primary,
    minHeight: 44,
    justifyContent: 'center',
  },
  emptyCtaText: { color: '#FFFFFF', fontSize: 14, fontWeight: '700' },
});
