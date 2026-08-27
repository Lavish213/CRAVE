// app/leaderboard.tsx
//
// Ranked by how many places you've logged, not by average score — logging
// breadth is the behaviour worth rewarding, and an average-score board
// would just reward rating everything a 10.
//
// The Global/Friends toggle exists because one global list is demoralising
// for anyone who isn't already a power user: a friends-scoped board is a
// race you can actually place in.
import React, { useCallback, useState } from 'react';
import {
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { Image } from 'expo-image';
import { useFocusEffect, useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import * as Haptics from 'expo-haptics';

import { Colors, Radius, Spacing } from '../src/constants/colors';
import { EmptyState } from '../src/components/EmptyState';
import { SkeletonRowList } from '../src/components/SkeletonCard';
import { LeaderboardRow, fetchLeaderboard } from '../src/api/social';
import { withImageWidth, AVATAR_IMAGE_WIDTH } from '../src/utils/imageUrl';
import { useAuthStore } from '../src/stores/authStore';

type Scope = 'global' | 'friends';

function medalFor(rank: number): string | null {
  if (rank === 1) return '🥇';
  if (rank === 2) return '🥈';
  if (rank === 3) return '🥉';
  return null;
}

export default function LeaderboardScreen() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  const [scope, setScope] = useState<Scope>('global');

  // Previously raw useState + useFocusEffect with no caching at all -- every
  // tab focus (including just switching Global/Friends and back) re-fetched
  // from scratch, unlike every other list screen in the app. staleTime
  // matches the home feed's -- the leaderboard doesn't need to be fresher
  // than that. The queryFn swallows errors into an empty array rather than
  // surfacing isError, matching this screen's original behavior exactly (no
  // distinct error copy existed here — a failed fetch and a genuinely empty
  // board both just showed the "nobody yet" EmptyState).
  const {
    data: rows = [],
    isLoading: loading,
    isRefetching: refreshing,
    refetch,
  } = useQuery({
    queryKey: ['leaderboard', scope],
    queryFn: () => fetchLeaderboard({ among: scope }).catch(() => []),
    staleTime: 2 * 60 * 1000,
  });

  // Cached data shows instantly on refocus; this just revalidates quietly
  // in the background instead of resetting to a full loading state.
  useFocusEffect(
    useCallback(() => {
      refetch();
    }, [refetch]),
  );

  const switchScope = (next: Scope) => {
    if (next === scope) return;
    Haptics.selectionAsync();
    setScope(next);
  };

  return (
    <View style={styles.container}>
      <View style={styles.toggle}>
        {(['global', 'friends'] as Scope[]).map((s) => (
          <TouchableOpacity
            key={s}
            style={[styles.toggleBtn, scope === s ? styles.toggleBtnActive : null]}
            onPress={() => switchScope(s)}
            accessibilityRole="button"
            accessibilityState={{ selected: scope === s }}
            accessibilityLabel={s === 'global' ? 'Global leaderboard' : 'Friends leaderboard'}
          >
            <Text style={[styles.toggleText, scope === s ? styles.toggleTextActive : null]}>
              {s === 'global' ? 'Global' : 'Friends'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.skeletonWrap}>
          <SkeletonRowList count={7} avatar />
        </View>
      ) : rows.length === 0 ? (
        <EmptyState
          icon="trophy-outline"
          title={scope === 'friends' ? 'No friends ranked yet' : 'Nobody on the board yet'}
          body={
            scope === 'friends'
              ? 'Follow people who rank places and they’ll show up here.'
              : 'Be the first — rank a place you’ve eaten at and you’ll take the top spot.'
          }
        />
      ) : (
        <FlashList
          data={rows}
          keyExtractor={(r) => r.user_id}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => refetch()}
              tintColor={Colors.primary}
            />
          }
          renderItem={({ item }) => {
            const isMe = item.user_id === user?.id;
            const label = item.display_name ?? (item.username ? `@${item.username}` : 'Someone');
            const medal = medalFor(item.rank);

            return (
              <TouchableOpacity
                style={[styles.row, isMe ? styles.rowMe : null]}
                activeOpacity={0.75}
                disabled={isMe}
                onPress={() => router.push(`/user/${item.user_id}`)}
                accessibilityRole="button"
                accessibilityLabel={`${label}, rank ${item.rank}, ${item.places_logged} places logged`}
              >
                <Text style={styles.rank}>{medal ?? item.rank}</Text>

                {item.avatar_url ? (
                  <Image
                    source={withImageWidth(item.avatar_url, AVATAR_IMAGE_WIDTH)}
                    style={styles.avatar}
                    contentFit="cover"
                    cachePolicy="memory-disk"
                  />
                ) : (
                  <View style={[styles.avatar, styles.avatarFallback]}>
                    <Text style={styles.avatarInitial}>
                      {label.replace('@', '').charAt(0).toUpperCase()}
                    </Text>
                  </View>
                )}

                <View style={styles.meta}>
                  <Text style={styles.name} numberOfLines={1}>
                    {label}
                    {isMe ? <Text style={styles.you}>  you</Text> : null}
                  </Text>
                  {item.username && item.display_name ? (
                    <Text style={styles.handle} numberOfLines={1}>
                      @{item.username}
                    </Text>
                  ) : null}
                </View>

                <View style={styles.countWrap}>
                  <Text style={styles.count}>{item.places_logged}</Text>
                  <Text style={styles.countLabel}>ranked</Text>
                </View>
              </TouchableOpacity>
            );
          }}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  skeletonWrap: { padding: Spacing.md },
  toggle: {
    flexDirection: 'row',
    gap: Spacing.xs,
    margin: Spacing.md,
    padding: 4,
    backgroundColor: Colors.surface,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  toggleBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 40,
  },
  toggleBtnActive: { backgroundColor: Colors.primary },
  toggleText: { color: Colors.textSecondary, fontSize: 14, fontWeight: '700' },
  toggleTextActive: { color: '#FFFFFF' },

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
  rowMe: { borderColor: Colors.primary },
  rank: {
    color: Colors.textSecondary,
    fontSize: 16,
    fontWeight: '800',
    minWidth: 28,
    textAlign: 'center',
  },
  avatar: { width: 40, height: 40, borderRadius: Radius.full, backgroundColor: Colors.surfaceElevated },
  avatarFallback: { alignItems: 'center', justifyContent: 'center' },
  avatarInitial: { color: Colors.text, fontSize: 16, fontWeight: '800' },
  meta: { flex: 1 },
  name: { color: Colors.text, fontSize: 15, fontWeight: '700' },
  you: { color: Colors.primary, fontSize: 12, fontWeight: '800' },
  handle: { color: Colors.textSecondary, fontSize: 12, marginTop: 1 },
  countWrap: { alignItems: 'flex-end' },
  count: { color: Colors.text, fontSize: 17, fontWeight: '800' },
  countLabel: { color: Colors.textSecondary, fontSize: 11 },
});
