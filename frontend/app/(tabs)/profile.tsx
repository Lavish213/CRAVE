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
  TasteProfile,
  fetchMyProfile,
  fetchMyRankings,
  fetchTasteProfile,
} from '../../src/api/social';
import {
  RECOMMENDATION_THRESHOLD,
  recommendationProgress,
} from '../../src/utils/rankScore';

export default function ProfileScreen() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  const [profile, setProfile] = useState<Profile | null>(null);
  const [rankings, setRankings] = useState<RankedPlace[]>([]);
  const [taste, setTaste] = useState<TasteProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [authVisible, setAuthVisible] = useState(false);
  const [profileError, setProfileError] = useState(false);
  const [rankingsError, setRankingsError] = useState(false);
  const [tasteError, setTasteError] = useState(false);

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
      setTaste(null);
      setLoading(true);
    }
    setProfileError(false);
    setRankingsError(false);
    setTasteError(false);
    try {
      const [p, r, t] = await Promise.all([
        fetchMyProfile().then((value) => ({ value, failed: false })).catch(() => ({ value: null, failed: true })),
        fetchMyRankings().then((value) => ({ value, failed: false })).catch(() => ({ value: [] as RankedPlace[], failed: true })),
        fetchTasteProfile(user.id).then((value) => ({ value, failed: false })).catch(() => ({ value: null, failed: true })),
      ]);
      if (myGeneration !== loadGenerationRef.current) return;
      loadedForUserIdRef.current = user.id;
      setProfile(p.value);
      setRankings(r.value);
      setTaste(t.value);
      setProfileError(p.failed);
      setRankingsError(r.failed);
      setTasteError(t.failed);
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

      <TouchableOpacity
        style={styles.tasteSummary}
        onPress={() => router.push(`/taste-profile/${user.id}`)}
        accessibilityRole="button"
        accessibilityLabel="Open your private Taste Profile"
      >
        <Text style={styles.headline} accessibilityRole="header">
          {tasteError || rankingsError
            ? 'Your private Taste Profile is temporarily unavailable.'
            : taste?.top_city
              ? `${rankings.length} ${rankings.length === 1 ? 'place' : 'places'} ranked. Most of your food history is in ${taste.top_city.name}.`
              : `${rankings.length} ${rankings.length === 1 ? 'place' : 'places'} ranked. CRAVE is still learning your taste.`}
        </Text>
        <Ionicons name="chevron-forward" size={18} color={Colors.textSecondary} />
      </TouchableOpacity>

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
  headline: { color: Colors.text, fontSize: 17, fontWeight: '700', lineHeight: 23 },
  tasteSummary: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
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
});
