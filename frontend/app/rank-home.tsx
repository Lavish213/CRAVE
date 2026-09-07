import React from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';

import { fetchRankQueue } from '../src/api/rankHome';
import { fetchMyRankings } from '../src/api/social';
import { EmptyState } from '../src/components/EmptyState';
import { ErrorState } from '../src/components/ErrorState';
import { RankQueueRow } from '../src/components/RankQueueRow';
import { RankedPlaceRow } from '../src/components/RankedPlaceRow';
import { SkeletonRowList } from '../src/components/SkeletonCard';
import { Colors, Spacing, Typography } from '../src/constants/colors';
import { useAuthStore } from '../src/stores/authStore';
import { requestAuthGate } from '../src/stores/authGateStore';

export default function RankHomeScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  const queueQuery = useQuery({
    queryKey: ['rankQueue', user?.id],
    queryFn: () => fetchRankQueue(),
    enabled: Boolean(user?.id),
  });
  const rankingsQuery = useQuery({
    queryKey: ['myRankings', user?.id],
    queryFn: fetchMyRankings,
    enabled: Boolean(user?.id),
  });

  if (!user) {
    return (
      <EmptyState
        icon="podium-outline"
        title="Sign in to rank places"
        body="Rank is your private record of places you've actually tried."
        ctaLabel="Sign in"
        onCta={() => requestAuthGate({
          actionType: 'open_rank_home',
          reason: 'rank',
          sourceRoute: '/rank-home',
          destination: '/rank-home',
          idempotent: true,
          resume: () => undefined,
        })}
      />
    );
  }

  const loading = queueQuery.isLoading || rankingsQuery.isLoading;
  const refreshing = queueQuery.isFetching || rankingsQuery.isFetching;
  const queue = queueQuery.data ?? [];
  const rankings = rankingsQuery.data ?? [];
  const visibleRankings = rankings.filter((item) => item.tier !== 'disliked');
  const liked = visibleRankings.filter((item) => item.tier === 'liked');
  const fine = visibleRankings.filter((item) => item.tier === 'fine');

  const refresh = () => {
    void Promise.all([queueQuery.refetch(), rankingsQuery.refetch()]);
  };

  if (loading) {
    return <View style={styles.loading}><SkeletonRowList count={5} /></View>;
  }

  if (queueQuery.isError && rankingsQuery.isError) {
    return <ErrorState message="Couldn't load Rank" onRetry={refresh} />;
  }

  if (queue.length === 0 && rankings.length === 0) {
    return (
      <EmptyState
        icon="podium-outline"
        title="Your Rank starts after a real visit"
        body="Mark a place you've visited, then come back here to compare it with the places you already know."
        ctaLabel="Browse places"
        onCta={() => router.push('/')}
      />
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={Colors.primary} />}
    >
      <View style={styles.header}>
        <Text style={styles.title}>Rank</Text>
        <Text style={styles.subtitle}>Teach CRAVE what you actually prefer.</Text>
      </View>

      {queueQuery.isError ? (
        <ErrorState message="Couldn't load places waiting to be ranked" onRetry={() => void queueQuery.refetch()} />
      ) : queue.length > 0 ? (
        <View style={styles.section}>
          <View style={styles.sectionHeadingRow}>
            <Text style={styles.sectionTitle}>Waiting to be ranked</Text>
            <Text style={styles.count}>{queue.length}</Text>
          </View>
          <View style={styles.list}>
            {queue.map((item) => (
              <RankQueueRow
                key={item.place_id}
                item={item}
                onPress={() => router.push(`/rank/${item.place_id}`)}
              />
            ))}
          </View>
        </View>
      ) : null}

      {rankingsQuery.isError ? (
        <ErrorState message="Couldn't load your ranked places" onRetry={() => void rankingsQuery.refetch()} />
      ) : visibleRankings.length > 0 ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Your ranked places</Text>
          {liked.length > 0 ? (
            <View style={styles.group}>
              <Text style={styles.groupTitle}>Loved it</Text>
              <View style={styles.list}>
                {liked.map((item, index) => (
                  <RankedPlaceRow
                    key={item.place_id}
                    position={index + 1}
                    name={item.name ?? 'Unknown place'}
                    imageUrl={item.primary_image_url}
                    score={item.rank_score}
                    tier={item.tier}
                    note={item.note}
                    showPosition={false}
                    showScore={false}
                    showTierLabel={false}
                    onPress={() => router.push(`/place/${item.place_id}`)}
                  />
                ))}
              </View>
            </View>
          ) : null}
          {fine.length > 0 ? (
            <View style={styles.group}>
              <Text style={styles.groupTitle}>It was fine</Text>
              <View style={styles.list}>
                {fine.map((item, index) => (
                  <RankedPlaceRow
                    key={item.place_id}
                    position={index + 1}
                    name={item.name ?? 'Unknown place'}
                    imageUrl={item.primary_image_url}
                    score={item.rank_score}
                    tier={item.tier}
                    note={item.note}
                    showPosition={false}
                    showScore={false}
                    showTierLabel={false}
                    onPress={() => router.push(`/place/${item.place_id}`)}
                  />
                ))}
              </View>
            </View>
          ) : null}
        </View>
      ) : null}

      <TouchableOpacity
        style={styles.explain}
        onPress={() => router.push(`/taste-profile/${user.id}`)}
        accessibilityRole="button"
        accessibilityLabel="Open your Taste Profile"
      >
        <Ionicons name="restaurant-outline" size={18} color={Colors.primary} />
        <Text style={styles.explainText}>See what CRAVE is learning from your choices</Text>
        <Ionicons name="chevron-forward" size={16} color={Colors.textSecondary} />
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.lg, paddingBottom: Spacing.xxl, gap: Spacing.xl },
  loading: { flex: 1, backgroundColor: Colors.background, padding: Spacing.lg },
  header: { gap: Spacing.xs },
  title: { ...Typography.headline, color: Colors.text },
  subtitle: { ...Typography.body, color: Colors.textSecondary },
  section: { gap: Spacing.md },
  sectionHeadingRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  sectionTitle: { ...Typography.subtitle, color: Colors.text },
  count: { ...Typography.caption, color: Colors.textSecondary },
  group: { gap: Spacing.sm },
  groupTitle: { ...Typography.label, color: Colors.textSecondary },
  list: { gap: Spacing.sm },
  explain: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  explainText: { ...Typography.body, color: Colors.text, flex: 1 },
});
