import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Animated,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { FlashList, ViewToken } from '@shopify/flash-list';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useInfiniteQuery } from '@tanstack/react-query';
import { fetchPlaces, PlaceOut } from '../../src/api/places';
import { useCityStore } from '../../src/stores/cityStore';
import { useCravesStore } from '../../src/stores/cravesStore';
import { useToast } from '../../src/hooks/useToast';
import { useTrending } from '../../src/hooks/useTrending';
import { useRecommendations } from '../../src/hooks/useRecommendations';
import { useLocation } from '../../src/hooks/useLocation';
import { usePrefetchPlace } from '../../src/hooks/usePrefetchPlace';
import { Colors, Spacing } from '../../src/constants/colors';
import { getTierForPlace, TIERS, TierKey } from '../../src/utils/scoring';
import { logRecommendationEvent, logRecommendationEvents } from '../../src/utils/recommendationEventQueue';
import { PlaceCard } from '../../src/components/PlaceCard';
import { SectionHeader } from '../../src/components/SectionHeader';
import { CitySelectorStrip } from '../../src/components/CitySelectorStrip';
import { TrendingStrip } from '../../src/components/TrendingStrip';
import { ErrorState } from '../../src/components/ErrorState';
import { EmptyState } from '../../src/components/EmptyState';
import { SkeletonFeed } from '../../src/components/SkeletonCard';
import { FilterSheet, FilterState, EMPTY_FILTERS, hasActiveFilters } from '../../src/components/FilterSheet';
import { useAuthStore } from '../../src/stores/authStore';
import { AuthSheet } from '../../src/components/AuthSheet';
import { useDecisionSession } from '../../src/hooks/useDecisionSession';
import { DecisionReasonCode, DecisionSessionCard } from '../../src/api/decisionSession';

const SHOW_FEED_DISCOVERY_STRIPS = false;
const VIEWABILITY_CONFIG = { itemVisiblePercentThreshold: 50, minimumViewTime: 250 };

const DECISION_REASON_COPY: Record<DecisionReasonCode, string> = {
  top_ranked_in_area: 'Top pick near you',
  high_percentile: 'One of the area’s strongest picks',
  close_by: 'Close by',
  underrated_pick: 'An underrated option worth considering',
  different_cuisine: 'Something different from your other picks',
};

function decisionReason(card: DecisionSessionCard): string | undefined {
  const reason = card.reason_codes[0];
  return reason ? DECISION_REASON_COPY[reason] : undefined;
}

type FeedRow =
  | { kind: 'decision'; card: DecisionSessionCard; position: number }
  | { kind: 'header'; tierKey: TierKey; count: number }
  | { kind: 'place'; place: PlaceOut };

function buildFeedRows(places: PlaceOut[]): FeedRow[] {
  const buckets: Record<TierKey, PlaceOut[]> = {
    crave_pick: [],
    gem: [],
    solid: [],
    new: [],
  };
  for (const p of places) buckets[getTierForPlace(p).key].push(p);

  const order: TierKey[] = ['crave_pick', 'gem', 'solid', 'new'];
  const rows: FeedRow[] = [];
  for (const key of order) {
    const section = buckets[key];
    if (section.length === 0) continue;
    rows.push({ kind: 'header', tierKey: key, count: section.length });
    for (const place of section) rows.push({ kind: 'place', place });
  }
  return rows;
}

export default function FeedScreen() {
  const router = useRouter();
  const prefetchPlace = usePrefetchPlace();
  const selectedCity = useCityStore((s) => s.selectedCity);
  const initCities = useCityStore((s) => s.initCities);
  const { addSave, removeSave, isSaved } = useCravesStore();
  const toast = useToast((s) => s.show);

  const userLocation = useLocation();
  // Keep hook ordering stable while honoring the feature flag: hidden
  // discovery strips must not keep fetching invisible data in background.
  const trending = useTrending(SHOW_FEED_DISCOVERY_STRIPS);
  const recommendations = useRecommendations(SHOW_FEED_DISCOVERY_STRIPS);
  const decisionSession = useDecisionSession();
  const decisionCards = decisionSession.data?.cards ?? [];

  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const radiusMiles = 20;
  const [authVisible, setAuthVisible] = useState(false);
  const user = useAuthStore((s) => s.user);
  const feedOpacity = useRef(new Animated.Value(0)).current;

  const feedParams = useMemo(() => ({
    city_id: selectedCity?.id,
    page_size: 40,
    radius_miles: radiusMiles,
    ...(userLocation && !selectedCity ? { lat: userLocation.lat, lng: userLocation.lng } : {}),
  }), [selectedCity?.id, radiusMiles, userLocation?.lat, userLocation?.lng]);

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    isError,
    refetch,
  } = useInfiniteQuery({
    queryKey: ['feed', feedParams],
    queryFn: ({ pageParam }) =>
      fetchPlaces({
        ...feedParams,
        pagination: 'cursor',
        cursor: pageParam,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    staleTime: 2 * 60 * 1000,
  });

  const places = useMemo(() => {
    const seen = new Set<string>();
    const result: PlaceOut[] = [];
    for (const page of data?.pages ?? []) {
      for (const p of page.items) {
        if (seen.has(p.id)) continue;
        seen.add(p.id);
        result.push(p);
      }
    }
    return result;
  }, [data]);

  const total = data?.pages[0]?.total ?? 0;
  const initialLoaded = data !== undefined || isError;

  if (__DEV__ && data) {
    const lastPage = data.pages[data.pages.length - 1];
    console.log('[FEED] PLACES_LOADED', {
      page: lastPage?.page,
      count: places.length,
      total,
      sample: places[0]
        ? { id: places[0].id, category: places[0].category, categories: places[0].categories }
        : null,
    });
  }

  const availableCategories = useMemo(() => {
    const names = new Set<string>();
    for (const p of places) {
      for (const c of p.categories ?? []) names.add(c);
    }
    return Array.from(names);
  }, [places]);

  useEffect(() => {
    initCities();
  }, [initCities]);

  useEffect(() => {
    if (initialLoaded && !isError) {
      Animated.timing(feedOpacity, {
        toValue: 1,
        duration: 350,
        useNativeDriver: true,
      }).start();
    }
  }, [initialLoaded, isError, feedOpacity]);

  useEffect(() => {
    feedOpacity.setValue(0);
  }, [selectedCity?.id, userLocation?.lat, userLocation?.lng, radiusMiles, feedOpacity]);

  const handleRefresh = () => {
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    void refetch();
  };

  const handleEndReached = () => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage();
  };

  const filteredPlaces = useMemo(() => {
    if (!hasActiveFilters(filters)) return places;
    return places.filter((p) => {
      if (
        filters.priceTiers.length > 0 &&
        (p.price_tier == null || !filters.priceTiers.includes(p.price_tier))
      ) return false;
      if (
        filters.categories.length > 0 &&
        !p.categories.some((c) => filters.categories.includes(c))
      ) return false;
      return true;
    });
  }, [places, filters]);

  const placeRows = useMemo(() => buildFeedRows(filteredPlaces), [filteredPlaces]);
  const rows = useMemo<FeedRow[]>(() => [
    ...decisionCards.map((card, position) => ({ kind: 'decision' as const, card, position })),
    ...placeRows,
  ], [decisionCards, placeRows]);

  // The position metric is defined among actual place cards, not section
  // headers. Tier bucketing changes display order relative to raw API order,
  // so derive positions from the rendered row stream rather than `places`.
  const renderedPlacePositions = useMemo(() => {
    const positions = new Map<string, number>();
    let position = 0;
    for (const row of placeRows) {
      if (row.kind !== 'place') continue;
      positions.set(row.place.id, position++);
    }
    return positions;
  }, [placeRows]);

  // Candidate retrieval is not an impression. A card must be at least 50%
  // visible for 250ms. This same stream covers both normal Feed places and
  // Decision Session cards, which previously logged all three as soon as
  // their data arrived even when the user never saw them.
  const exposedKeysRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    exposedKeysRef.current = new Set();
  }, [selectedCity?.id, userLocation?.lat, userLocation?.lng, radiusMiles]);

  const handleViewableItemsChangedRef = useRef<(
    info: { viewableItems: ViewToken<FeedRow>[] }
  ) => void>(() => {});

  handleViewableItemsChangedRef.current = (info) => {
    const events: Parameters<typeof logRecommendationEvents>[0] = [];

    for (const token of info.viewableItems) {
      if (!token.isViewable || !token.item) continue;
      const row = token.item;

      if (row.kind === 'place') {
        const exposureKey = `feed:${row.place.id}`;
        if (exposedKeysRef.current.has(exposureKey)) continue;
        exposedKeysRef.current.add(exposureKey);
        events.push({
          surface: 'feed',
          event_type: 'impression',
          place_id: row.place.id,
          position: renderedPlacePositions.get(row.place.id) ?? null,
          rank_percentile: row.place.rank_percentile,
          city_id: selectedCity?.id ?? null,
        });
        continue;
      }

      if (row.kind === 'decision') {
        const exposureKey = `decision:${row.card.role}:${row.card.place.id}`;
        if (exposedKeysRef.current.has(exposureKey)) continue;
        exposedKeysRef.current.add(exposureKey);
        events.push({
          surface: 'decision_session',
          event_type: 'impression',
          place_id: row.card.place.id,
          position: row.position,
          rank_percentile: row.card.place.rank_percentile,
          city_id: selectedCity?.id ?? null,
          decision_role: row.card.role,
        });
      }
    }

    if (events.length > 0) logRecommendationEvents(events);
  };

  const onViewableItemsChanged = useRef((info: { viewableItems: ViewToken<FeedRow>[] }) => {
    handleViewableItemsChangedRef.current(info);
  }).current;

  const renderDecisionCard = (card: DecisionSessionCard, position: number) => (
    <View style={styles.rowSpacer}>
      <PlaceCard
        place={card.place}
        role={card.role}
        reasonCaption={decisionReason(card)}
        onPress={() => {
          logRecommendationEvent({
            surface: 'decision_session',
            event_type: 'click',
            place_id: card.place.id,
            position,
            rank_percentile: card.place.rank_percentile,
            city_id: selectedCity?.id ?? null,
            decision_role: card.role,
          });
          router.push(`/place/${card.place.id}`);
        }}
        onPressIn={() => prefetchPlace(card.place.id)}
        onSave={async () => {
          if (!user) {
            setAuthVisible(true);
            return;
          }
          const saveMeta = {
            surface: 'decision_session' as const,
            position,
            rank_percentile: card.place.rank_percentile,
            city_id: selectedCity?.id ?? null,
          };
          if (isSaved(card.place.id)) {
            void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
            const err = await removeSave(card.place.id, user.id, saveMeta);
            toast(err ?? 'Removed from Saves');
          } else {
            void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
            const err = await addSave(card.place, user.id, saveMeta);
            toast(err ?? 'Saved');
          }
        }}
        saved={isSaved(card.place.id)}
        style={styles.decisionCard}
      />
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.wordmark}>CRAVE</Text>
        <View style={styles.spacer} />
        <TouchableOpacity
          style={styles.filterBtn}
          onPress={() => {
            void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
            setFilterVisible(true);
          }}
          accessibilityLabel="Filter places"
          accessibilityRole="button"
        >
          <Ionicons
            name="options-outline"
            size={20}
            color={hasActiveFilters(filters) ? Colors.primary : Colors.textSecondary}
          />
        </TouchableOpacity>
      </View>

      <CitySelectorStrip />
      {SHOW_FEED_DISCOVERY_STRIPS && user ? (
        <TrendingStrip
          places={recommendations}
          heading="RECOMMENDED FOR YOU"
          onPress={(id) => router.push(`/place/${id}`)}
          onPressIn={prefetchPlace}
        />
      ) : null}
      {SHOW_FEED_DISCOVERY_STRIPS ? (
        <TrendingStrip
          places={trending}
          onPress={(id) => router.push(`/place/${id}`)}
          onPressIn={prefetchPlace}
        />
      ) : null}

      {!initialLoaded ? (
        <View style={styles.skeletonWrap}><SkeletonFeed count={4} /></View>
      ) : (
        <Animated.View style={[{ flex: 1 }, { opacity: feedOpacity }]}>
          {isError ? (
            <ErrorState message="Couldn't load places" onRetry={() => void refetch()} />
          ) : rows.length === 0 ? (
            <EmptyState
              icon="search-outline"
              title="Nothing here yet"
              body={selectedCity ? 'Try selecting a different city' : 'No places found'}
            />
          ) : (
            <FlashList
              data={rows}
              keyExtractor={(row, i) => {
                if (row.kind === 'place') return row.place.id;
                if (row.kind === 'decision') return `decision-${row.card.role}-${row.card.place.id}`;
                return `header-${row.tierKey}-${i}`;
              }}
              getItemType={(row) => row.kind}
              renderItem={({ item: row }) => {
                if (row.kind === 'decision') {
                  return renderDecisionCard(row.card, row.position);
                }
                if (row.kind === 'header') {
                  const tier = TIERS[row.tierKey];
                  return (
                    <View style={styles.rowSpacer}>
                      <SectionHeader
                        label={tier.sectionLabel}
                        subtext={tier.sectionSubtext}
                        count={row.count}
                      />
                    </View>
                  );
                }

                const position = renderedPlacePositions.get(row.place.id) ?? null;
                return (
                  <View style={styles.rowSpacer}>
                    <PlaceCard
                      place={row.place}
                      onPress={() => {
                        logRecommendationEvent({
                          surface: 'feed',
                          event_type: 'click',
                          place_id: row.place.id,
                          position,
                          rank_percentile: row.place.rank_percentile,
                          city_id: selectedCity?.id ?? null,
                        });
                        router.push(`/place/${row.place.id}`);
                      }}
                      onPressIn={() => prefetchPlace(row.place.id)}
                      onSave={async () => {
                        if (!user) {
                          setAuthVisible(true);
                          return;
                        }
                        const saveMeta = {
                          surface: 'feed' as const,
                          position,
                          rank_percentile: row.place.rank_percentile,
                          city_id: selectedCity?.id ?? null,
                        };
                        if (isSaved(row.place.id)) {
                          void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
                          const err = await removeSave(row.place.id, user.id, saveMeta);
                          toast(err ?? 'Removed from Saves');
                        } else {
                          void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
                          const err = await addSave(row.place, user.id, saveMeta);
                          toast(err ?? 'Saved');
                        }
                      }}
                      saved={isSaved(row.place.id)}
                    />
                  </View>
                );
              }}
              contentContainerStyle={styles.list}
              onEndReached={handleEndReached}
              onEndReachedThreshold={0.3}
              viewabilityConfig={VIEWABILITY_CONFIG}
              onViewableItemsChanged={onViewableItemsChanged}
              refreshControl={
                <RefreshControl
                  refreshing={isFetching && !isFetchingNextPage && initialLoaded}
                  onRefresh={handleRefresh}
                  tintColor={Colors.primary}
                />
              }
              ListHeaderComponent={
                decisionCards.length > 0 ? (
                  <View style={styles.decisionSectionHeader}>
                    <Text style={styles.decisionHeading}>DECIDE NOW</Text>
                    <Text style={styles.decisionSubheading}>
                      Three different ways to answer what should I eat?
                    </Text>
                  </View>
                ) : null
              }
              ListFooterComponent={
                isFetchingNextPage
                  ? <ActivityIndicator color={Colors.primary} style={styles.listFooter} />
                  : null
              }
            />
          )}
        </Animated.View>
      )}

      <FilterSheet
        visible={filterVisible}
        onClose={() => setFilterVisible(false)}
        filters={filters}
        onChange={setFilters}
        availableCategories={availableCategories}
      />
      <AuthSheet
        visible={authVisible}
        onClose={() => setAuthVisible(false)}
        reason="save"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  list: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.xxl },
  rowSpacer: { marginBottom: Spacing.md },
  decisionSectionHeader: { paddingTop: Spacing.sm },
  decisionHeading: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '900',
    letterSpacing: 1.5,
    marginBottom: Spacing.xs,
  },
  decisionSubheading: {
    color: Colors.textSecondary,
    fontSize: 13,
    marginBottom: Spacing.md,
  },
  decisionCard: { marginBottom: 0 },
  listFooter: { margin: Spacing.lg },
  skeletonWrap: { flex: 1, paddingHorizontal: 12, paddingTop: 10 },
  header: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
  },
  wordmark: { fontSize: 26, fontWeight: '900', color: Colors.primary, letterSpacing: 3 },
  filterBtn: {
    padding: Spacing.sm,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  spacer: { flex: 1 },
});
