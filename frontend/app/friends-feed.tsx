// app/friends-feed.tsx
//
// "Your friend just ranked X" — the payoff for having a follow graph at
// all. Deliberately separate from the algorithmic catalog feed on the home
// tab: this one is chronological, small, and empty until you follow people,
// and pretending otherwise by padding it with recommendations would make it
// indistinguishable from the home tab.
import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useRouter } from 'expo-router';

import { Colors, Radius, Spacing } from '../src/constants/colors';
import { EmptyState } from '../src/components/EmptyState';
import { ActivityEvent, fetchFriendsFeed } from '../src/api/social';
import { formatScore, tierColor } from '../src/utils/rankScore';
import { relativeTime } from '../src/utils/time';

function actorName(event: ActivityEvent): string {
  const a = event.actor;
  return a?.display_name ?? (a?.username ? `@${a.username}` : 'Someone');
}

export default function FriendsFeedScreen() {
  const router = useRouter();
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setEvents(await fetchFriendsFeed());
    } catch {
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, []);

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
    <FlatList
      style={styles.container}
      data={events}
      keyExtractor={(e) => e.id}
      contentContainerStyle={styles.list}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={async () => {
            setRefreshing(true);
            try {
              await load();
            } finally {
              setRefreshing(false);
            }
          }}
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
              <Image source={item.actor.avatar_url} style={styles.avatar} contentFit="cover" />
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
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.background,
  },
  list: { padding: Spacing.md, gap: Spacing.sm, paddingBottom: Spacing.xxl },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    padding: Spacing.md,
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
