import React from 'react';
import { RefreshControl, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { Colors, Radius, Spacing } from '../src/constants/colors';
import { EmptyState } from '../src/components/EmptyState';
import { ErrorState } from '../src/components/ErrorState';
import { SkeletonRowList } from '../src/components/SkeletonCard';
import { fetchMyActivity, type ActivityEvent } from '../src/api/social';
import { foundationQueryKey, STALE_TIME } from '../src/contracts/foundationGate';
import { requestAuthGate } from '../src/stores/authGateStore';
import { useAuthStore } from '../src/stores/authStore';
import { relativeTime } from '../src/utils/time';

function eventCopy(event: ActivityEvent): string {
  if (event.event_type === 'ranked_place') {
    return `You ranked ${event.place_name ?? 'a place'}`;
  }
  const target = event.target_user?.display_name
    ?? (event.target_user?.username ? `@${event.target_user.username}` : 'someone');
  return `You followed ${target}`;
}

export default function ActivityScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const { data, isLoading, isError, isRefetching, refetch } = useQuery({
    queryKey: user
      ? foundationQueryKey({ scope: 'user', entity: 'activity', userId: user.id })
      : ['crave', 'user', 'activity', null, null],
    queryFn: ({ signal }) => fetchMyActivity(30, 0, signal),
    enabled: Boolean(user),
    staleTime: STALE_TIME.short,
  });

  if (!user) {
    return (
      <EmptyState
        icon="notifications-outline"
        title="Sign in to see your activity"
        body="Your ranking and follow history will appear here."
        ctaLabel="Sign in"
        onCta={() => requestAuthGate({
          actionType: 'view_activity',
          reason: 'default',
          sourceRoute: '/activity',
          destination: '/activity',
          idempotent: true,
          resume: () => undefined,
        })}
      />
    );
  }

  if (isLoading) {
    return <View style={styles.loading}><SkeletonRowList count={5} /></View>;
  }

  if (isError && (!data || data.length === 0)) {
    return <ErrorState message="Couldn't load your activity" onRetry={() => void refetch()} />;
  }

  if (!data?.length) {
    return (
      <EmptyState
        icon="notifications-outline"
        title="No activity yet"
        body="Places you rank and people you follow will appear here."
      />
    );
  }

  return (
    <FlashList
      style={styles.container}
      data={data}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.list}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={() => void refetch()} tintColor={Colors.primary} />}
      ListHeaderComponent={isError ? (
        <Text style={styles.degraded} accessibilityRole="alert">
          You're viewing saved activity. Pull to try updating again.
        </Text>
      ) : null}
      renderItem={({ item }) => {
        const canOpenPlace = item.event_type === 'ranked_place' && Boolean(item.place_id);
        return (
          <TouchableOpacity
            style={styles.row}
            disabled={!canOpenPlace}
            activeOpacity={canOpenPlace ? 0.75 : 1}
            onPress={() => item.place_id && router.push(`/place/${item.place_id}`)}
            accessibilityRole={canOpenPlace ? 'button' : 'text'}
            accessibilityLabel={eventCopy(item)}
          >
            <View style={styles.icon}>
              <Ionicons
                name={item.event_type === 'ranked_place' ? 'star-outline' : 'person-add-outline'}
                size={20}
                color={Colors.primary}
              />
            </View>
            <View style={styles.body}>
              <Text style={styles.eventText}>{eventCopy(item)}</Text>
              <Text style={styles.time}>{relativeTime(item.created_at)}</Text>
            </View>
            {canOpenPlace ? <Ionicons name="chevron-forward" size={18} color={Colors.textSecondary} /> : null}
          </TouchableOpacity>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  loading: { flex: 1, padding: Spacing.md, backgroundColor: Colors.background },
  list: { padding: Spacing.md, paddingBottom: Spacing.xxl },
  degraded: { color: Colors.textSecondary, fontSize: 13, lineHeight: 18, marginBottom: Spacing.md },
  row: { minHeight: 64, flexDirection: 'row', alignItems: 'center', gap: Spacing.md, padding: Spacing.md, marginBottom: Spacing.sm, backgroundColor: Colors.surface, borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.border },
  icon: { width: 40, height: 40, borderRadius: Radius.full, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.surfaceElevated },
  body: { flex: 1 },
  eventText: { color: Colors.text, fontSize: 15, fontWeight: '600', lineHeight: 20 },
  time: { color: Colors.textSecondary, fontSize: 12, marginTop: 3 },
});
