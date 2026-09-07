// app/(tabs)/profile.tsx
//
// Identity-first Profile. Full personal ranking ownership lives in Rank Home;
// Profile keeps only a compact status/link so state ownership is not split.
import React, { useCallback, useRef, useState } from 'react';
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
import { ErrorState } from '../../src/components/ErrorState';
import { AuthSheet } from '../../src/components/AuthSheet';
import { SkeletonRowList } from '../../src/components/SkeletonCard';
import { withImageWidth, AVATAR_IMAGE_WIDTH } from '../../src/utils/imageUrl';
import { useAuthStore } from '../../src/stores/authStore';
import {
  Profile,
  RankedPlace,
  fetchFollowers,
  fetchFollowing,
  fetchMyProfile,
  fetchMyRankings,
} from '../../src/api/social';
import { Streak, fetchMyStreak } from '../../src/api/streak';
import {
  RECOMMENDATION_THRESHOLD,
  rankedListHeadline,
  recommendationProgress,
} from '../../src/utils/rankScore';

function StatTile({
  value,
  label,
  onPress,
  icon,
}: {
  value: number | string;
  label: string;
  onPress?: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
}) {
  const inner = (
    <View style={styles.statTile}>
      <View style={styles.statValueRow}>
        {icon ? <Ionicons name={icon} size={16} color={Colors.primary} /> : null}
        <Text style={styles.statValue}>{value}</Text>
      </View>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
  if (!onPress) return inner;
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.75}
      accessibilityRole="button"
      accessibilityLabel={`${value} ${label}`}
      style={{ flex: 1 }}
    >
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
  const [streak, setStreak] = useState<Streak | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [authVisible, setAuthVisible] = useState(false);
  const [profileError, setProfileError] = useState(false);
  const [rankingsError, setRankingsError] = useState(false);
  const [followingError, setFollowingError] = useState(false);
  const [followersError, setFollowersError] = useState(false);
  const [streakError, setStreakError] = useState(false);

  const loadGenerationRef = useRef(0);
  const loadedForUserIdRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    const myGeneration = ++loadGenerationRef.current;
    if (!user) {
      loadedForUserIdRef.current = null;
      setLoading(false);
      return;
    }
    if (loadedForUserIdRef.current !== user.id) {
      setProfile(null);
      setRankings([]);
      setFollowingCount(0);
      setFollowerCount(0);
      setStreak(null);
      setLoading(true);
    }
    setProfileError(false);
    setRankingsError(false);
    setFollowingError(false);
    setFollowersError(false);
    setStreakError(false);
    try {
      const [p, r, following, followers, s] = await Promise.all([
        fetchMyProfile().then((value) => ({ value, failed: false })).catch(() => ({ value: null, failed: true })),
        fetchMyRankings().then((value) => ({ value, failed: false })).catch(() => ({ value: [] as RankedPlace[], failed: true })),
        fetchFollowing().then((value) => ({ value, failed: false })).catch(() => ({ value: [] as string[], failed: true })),
        fetchFollowers().then((value) => ({ value, failed: false })).catch(() => ({ value: [] as string[], failed: true })),
        fetchMyStreak().then((value) => ({ value, failed: false })).catch(() => ({ value: null, failed: true })),
      ]);
      if (myGeneration !== loadGenerationRef.current) return;
      loadedForUserIdRef.current = user.id;
      setProfile(p.value);
      setRankings(r.value);
      setFollowingCount(following.value.length);
      setFollowerCount(followers.value.length);
      setStreak(s.value);
      setProfileError(p.failed);
      setRankingsError(r.failed);
      setFollowingError(following.failed);
      setFollowersError(followers.failed);
      setStreakError(s.failed);
    } finally {
      if (myGeneration === loadGenerationRef.current) setLoading(false);
    }
  }, [user?.id]);

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
          title="Sign in to build your food identity"
          body="Your profile is where CRAVE reflects what it has learned from your real choices."
          ctaLabel="Sign in"
          onCta={() => setAuthVisible(true)}
        />
        <AuthSheet visible={authVisible} onClose={() => setAuthVisible(false)} reason="profile" />
      </>
    );
  }

  const isStaleForCurrentUser = loadedForUserIdRef.current !== user.id;
  if (loading || isStaleForCurrentUser) {
    return (
      <View style={styles.content}>
        <SkeletonRowList count={4} />
      </View>
    );
  }

  if (profileError) {
    return <ErrorState message="Couldn't load your profile" onRetry={load} />;
  }

  if (!profile) {
    return (
      <EmptyState
        icon="at-outline"
        title="Pick a username"
        body="Choose the identity people can use to find you. Your private taste data stays separate."
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
          <Image
            source={withImageWidth(profile.avatar_url, AVATAR_IMAGE_WIDTH)}
            style={styles.avatar}
            contentFit="cover"
            cachePolicy="memory-disk"
          />
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
        <StatTile value={rankingsError ? '—' : rankings.length} label="ranked" onPress={() => router.push('/rank-home')} />
        <StatTile value={followersError ? '—' : followerCount} label="followers" />
        <StatTile value={followingError ? '—' : followingCount} label="following" />
        {streak && streak.current_streak > 0 ? (
          <StatTile value={streak.current_streak} label="day streak" icon="flame" />
        ) : streakError ? (
          <StatTile value="—" label="day streak" icon="flame" />
        ) : null}
      </View>

      {!rankingsError ? <Text style={styles.headline}>{rankedListHeadline(rankings.length)}</Text> : null}

      {!rankingsError && !unlocked ? (
        <View style={styles.unlockCard}>
          <Ionicons name="sparkles-outline" size={18} color={Colors.primary} />
          <Text style={styles.unlockText}>
            Rank {remaining} more {remaining === 1 ? 'place' : 'places'} to give CRAVE a stronger read on your taste.
          </Text>
        </View>
      ) : null}

      <TouchableOpacity
        style={styles.rankCard}
        onPress={() => router.push('/rank-home')}
        accessibilityRole="button"
        accessibilityLabel="Open Rank"
      >
        <View style={styles.rankIcon}>
          <Ionicons name="podium-outline" size={22} color={Colors.primary} />
        </View>
        <View style={styles.rankMeta}>
          <Text style={styles.rankTitle}>Rank</Text>
          <Text style={styles.rankBody}>
            {rankingsError
              ? "Open your ranking workspace"
              : rankings.length === 0
                ? "Start ranking places you've actually tried"
                : `${rankings.length} ${rankings.length === 1 ? 'place' : 'places'} ranked — manage comparisons in Rank`}
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={Colors.textSecondary} />
      </TouchableOpacity>

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
        {!rankingsError && rankings.length > 0 ? (
          <TouchableOpacity
            style={styles.linkBtn}
            onPress={() => router.push(`/taste-profile/${user.id}`)}
            accessibilityRole="button"
            accessibilityLabel="Your Taste Profile"
          >
            <Ionicons name="restaurant-outline" size={18} color={Colors.primary} />
            <Text style={styles.linkBtnText}>Taste Profile</Text>
          </TouchableOpacity>
        ) : null}
      </View>
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
  username: { color: Colors.textSecondary, fontSize: 14, marginTop: 1 },
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
  statValueRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  statValue: { color: Colors.text, fontSize: 22, fontWeight: '800' },
  statLabel: { color: Colors.textSecondary, fontSize: 12, marginTop: 2 },
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
  rankCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    padding: Spacing.md,
    minHeight: 72,
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  rankIcon: {
    width: 44,
    height: 44,
    borderRadius: Radius.full,
    backgroundColor: Colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rankMeta: { flex: 1, gap: 2 },
  rankTitle: { color: Colors.text, fontSize: 16, fontWeight: '800' },
  rankBody: { color: Colors.textSecondary, fontSize: 13, lineHeight: 18 },
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
});
