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
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { useFocusEffect, useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';

import { Colors, Radius, Spacing } from '../src/constants/colors';
import { EmptyState } from '../src/components/EmptyState';
import { LeaderboardRow, fetchLeaderboard } from '../src/api/social';
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
  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (which: Scope) => {
    try {
      setRows(await fetchLeaderboard({ among: which }));
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load(scope);
    }, [load, scope]),
  );

  const switchScope = (next: Scope) => {
    if (next === scope) return;
    Haptics.selectionAsync();
    setScope(next);
    setLoading(true);
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
        <View style={styles.centered}>
          <ActivityIndicator color={Colors.primary} size="large" />
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
        <FlatList
          data={rows}
          keyExtractor={(r) => r.user_id}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={async () => {
                setRefreshing(true);
                try {
                  await load(scope);
                } finally {
                  setRefreshing(false);
                }
              }}
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
                  <Image source={item.avatar_url} style={styles.avatar} contentFit="cover" />
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
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
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
  rowMe: { borderColor: Colors.primary },
  rank: {
    color: Colors.textMuted,
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
  handle: { color: Colors.textMuted, fontSize: 12, marginTop: 1 },
  countWrap: { alignItems: 'flex-end' },
  count: { color: Colors.text, fontSize: 17, fontWeight: '800' },
  countLabel: { color: Colors.textMuted, fontSize: 11 },
});
