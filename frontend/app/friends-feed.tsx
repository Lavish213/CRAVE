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
import { ErrorState } from '../src/components/ErrorState';
import { SkeletonRowList } from '../src/components/SkeletonCard';
import { ActivityEvent, fetchFriendsFeed } from '../src/api/social';
import { useAuthStore } from '../src/stores/authStore';
import { formatScore, tierColor } from '../src/utils/rankScore';
import { relativeTime } from '../src/utils/time';
import { withImageWidth, AVATAR_IMAGE_WIDTH } from '../src/utils/imageUrl';

function actorName(event: ActivityEvent): string {
  const actor = event.actor;
  return actor?.display_name ?? (actor?.username ? `@${actor.username}` : 'Someone');
}

function reactionCopy(reaction: ActivityEvent['payload'] extends infer P ? P extends { reaction?: infer R } ? R : never : never): string {
  if (reaction === 'loved') return 'Loved it';
  if (reaction === 'good') return 'Good';
  if (reaction === 'not_for_me') return 'Not for me';
  return 'Shared a food find';
}

export default function FriendsFeedScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const {
    data: events = [],
    isLoading: loading,
    isError,
    isRefetching: refreshing,
    refetch,
  } = useQuery({
    queryKey: ['friends-feed', user?.id],
    queryFn: () => fetchFriendsFeed(),
    staleTime: 2 * 60 * 1000,
    enabled: !!user,
  });

  useFocusEffect(
    useCallback(() => {
      if (!user) return;
      refetch();
    }, [user, refetch]),
  );

  if (loading) {
    return (
      <View style={styles.list}>
        <SkeletonRowList count={5} avatar />
      </View>
    );
  }

  if (isError) {
    return <ErrorState message="Couldn't load your friends feed" onRetry={() => user && refetch()} />;
  }

  if (events.length === 0) {
    return (
      <EmptyState
        icon="people-outline"
        title="Nothing here yet"
        body="Follow people to see food finds and ranking activity from accounts you follow."
        ctaLabel="Find people"
        onCta={() => router.push('/leaderboard')}
      />
    );
  }

  return (
    <FlashList
      style={styles.container}
      data={events}
      keyExtractor={(event) => event.id}
      contentContainerStyle={styles.list}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => user && refetch()}
          tintColor={Colors.primary}
        />
      }
      renderItem={({ item }) => {
        const isRanking = item.event_type === 'ranked_place';
        const isPost = item.event_type === 'posted_food';
        const score = item.payload?.score;
        const tier = item.payload?.tier;
        const canOpenPlace = (isRanking || isPost) && !!item.place_id;

        return (
          <TouchableOpacity
            style={styles.row}
            activeOpacity={canOpenPlace ? 0.75 : 1}
            disabled={!canOpenPlace}
            onPress={() => item.place_id && router.push(`/place/${item.place_id}`)}
            accessibilityRole="button"
            accessibilityLabel={
              isRanking
                ? `${actorName(item)} ranked ${item.place_name ?? 'a place'}`
                : isPost
                  ? `${actorName(item)} shared a food find at ${item.place_name ?? 'a place'}`
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
                ) : isPost ? (
                  <>
                    {' shared '}
                    <Text style={styles.subject}>{item.place_name ?? 'a food find'}</Text>
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
              {isPost ? <Text style={styles.postReaction}>{reactionCopy(item.payload?.reaction)}</Text> : null}
              <Text style={styles.time}>{relativeTime(item.created_at)}</Text>
            </View>

            {isRanking && typeof score === 'number' && tier ? (
              <View style={[styles.scorePill, { borderColor: tierColor(tier) }]}>
                <Text style={[styles.scoreText, { color: tierColor(tier) }]}>
                  {formatScore(score)}
                </Text>
              </View>
            ) : isPost ? (
              <Ionicons name="restaurant-outline" size={18} color={Colors.primary} />
            ) : (
              <Ionicons name="person-add-outline" size={16} color={Colors.textSecondary} />
            )}
          </TouchableOpacity>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
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
  postReaction: { color: Colors.text, fontSize: 12, fontWeight: '700', marginTop: 2 },
  time: { color: Colors.textSecondary, fontSize: 12, marginTop: 2 },
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
