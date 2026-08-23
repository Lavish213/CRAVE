// app/friends-feed.tsx
//
// "Your friend just ranked X" — the payoff for having a follow graph at
// all. Deliberately separate from the algorithmic catalog feed on the home
// tab: this one is chronological, small, and empty until you follow people,
// and pretending otherwise by padding it with recommendations would make it
// indistinguishable from the home tab.
import React, { useCallback } from 'react';
import {
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';

import { Colors, Radius, Spacing } from '../src/constants/colors';
import { EmptyState } from '../src/components/EmptyState';
import { SkeletonRowList } from '../src/components/SkeletonCard';
import { ActivityEvent, fetchFriendsFeed } from '../src/api/social';
import { formatScore, tierColor } from '../src/utils/rankScore';
import { relativeTime } from '../src/utils/time';
import { withImageWidth, AVATAR_IMAGE_WIDTH } from '../src/utils/imageUrl';

function actorName(event: ActivityEvent): string {
  const a = event.actor;
  return a?.display_name ?? (a?.username ? `@${a.username}` : 'Someone');
}

export default function FriendsFeedScreen() {
  const router = useRouter();
  // Previously raw useState + useFocusEffect with no caching at all -- every
  // tab focus re-fetched from scratch, unlike every other list screen in the
  // app. The queryFn swallows errors into an empty array, matching this
  // screen's original behavior exactly (no distinct error copy existed here
  // — a failed fetch and a genuinely empty feed both just showed the "follow
  // people" EmptyState).
  const {
    data: events = [],
    isLoading: loading,
    isRefetching: refreshing,
    refetch,
  } = useQuery({
    queryKey: ['friends-feed'],
    queryFn: () => fetchFriendsFeed().catch(() => []),
    staleTime: 2 * 60 * 1000,
  });

  // Cached data shows instantly on refocus; this just revalidates quietly
  // in the background instead of resetting to a full loading state.
  useFocusEffect(
    useCallback(() => {
      refetch();
    }, [refetch]),
  );

  if (loading) {
    return (
      <View style={styles.list}>
        <SkeletonRowList count={5} avatar />
      </View>
    );
  }

  if (events.length === 0) {
    return (
      <EmptyState
        icon="people-outline"
        title="Nothing here yet"
        body="Follow people to see what they're ranking. This feed only shows activity from accounts you follow."
        ctaLabel="Find people"
        onCta={() => router.push('/leaderboard')}
      />
    );
  }

  return (
    <FlashList
      style={styles.container}
      data={events}
      keyExtractor={(e) => e.id}
      contentContainerStyle={styles.list}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => refetch()}
          tintColor={Colors.primary}
        />
      }
      renderItem={({ item }) => {
        const isRanking = item.event_type === 'ranked_place';
        const score = item.payload?.score;
        const tier = item.payload?.tier;

        return (
          <TouchableOpacity
            style={styles.row}
            activeOpacity={isRanking && item.place_id ? 0.75 : 1}
            disabled={!isRanking || !item.place_id}
            onPress={() => item.place_id && router.push(`/place/${item.place_id}`)}
            accessibilityRole="button"
            accessibilityLabel={
              isRanking
                ? `${actorName(item)} ranked ${item.place_name ?? 'a place'}`
                : `${actorName(item)} followed someone`
            }
          >
            {item.actor?.avatar_url ? (
              <Image
                source={withImageWidth(item.actor.avatar_url, AVATAR_IMAGE_WIDTH)}
                style={styles.avatar}
                contentFit="cover"
                cachePolicy="memory-disk"
              />
            ) : (
              <View style={[styles.avatar, styles.avatarFallback]}>
                <Text style={styles.avatarInitial}>
                  {actorName(item).replace('@', '').charAt(0).toUpperCase()}
                </Text>
              </View>
            )}

            <View style={styles.body}>
              <Text style={styles.text} numberOfLines={2}>
                <Text style={styles.actor}>{actorName(item)}</Text>
                {isRanking ? (
                  <>
                    {' ranked '}
                    <Text style={styles.subject}>{item.place_name ?? 'a place'}</Text>
                  </>
                ) : (
                  <>
                    {' followed '}
                    <Text style={styles.subject}>
                      {item.target_user?.display_name ??
                        (item.target_user?.username ? `@${item.target_user.username}` : 'someone')}
                    </Text>
                  </>
                )}
              </Text>
              <Text style={styles.time}>{relativeTime(item.created_at)}</Text>
            </View>

            {isRanking && typeof score === 'number' && tier ? (
              <View style={[styles.scorePill, { borderColor: tierColor(tier) }]}>
                <Text style={[styles.scoreText, { color: tierColor(tier) }]}>
                  {formatScore(score)}
                </Text>
              </View>
            ) : (
              <Ionicons name="person-add-outline" size={16} color={Colors.textMuted} />
            )}
          </TouchableOpacity>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  // FlashList's contentContainerStyle doesn't reliably support `gap`
  // (unlike FlatList) -- https://github.com/Shopify/flash-list/issues/2097 --
  // so inter-row spacing is applied via row's marginBottom instead.
  list: { padding: Spacing.md, paddingBottom: Spacing.xxl },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  avatar: { width: 40, height: 40, borderRadius: Radius.full, backgroundColor: Colors.surfaceElevated },
  avatarFallback: { alignItems: 'center', justifyContent: 'center' },
  avatarInitial: { color: Colors.text, fontSize: 16, fontWeight: '800' },
  body: { flex: 1 },
  text: { color: Colors.textSecondary, fontSize: 14, lineHeight: 19 },
  actor: { color: Colors.text, fontWeight: '700' },
  subject: { color: Colors.text, fontWeight: '700' },
  time: { color: Colors.textMuted, fontSize: 12, marginTop: 2 },
  scorePill: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: Radius.pill,
    borderWidth: 1.5,
    minWidth: 44,
    alignItems: 'center',
  },
  scoreText: { fontSize: 14, fontWeight: '800' },
});
