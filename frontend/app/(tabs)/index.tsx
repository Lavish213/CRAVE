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
import { useRecommendations } from '../../src/hooks/useRecommendations';
import { useLocation } from '../../src/hooks/useLocation';
import { usePrefetchPlace } from '../../src/hooks/usePrefetchPlace';
import { Colors, Spacing } from '../../src/constants/colors';
import { getTierForPlace } from '../../src/utils/scoring';
import { logRecommendationEvent, logRecommendationEvents } from '../../src/utils/recommendationEventQueue';
import { PlaceCard } from '../../src/components/PlaceCard';
import { CitySelectorStrip } from '../../src/components/CitySelectorStrip';
import { ErrorState } from '../../src/components/ErrorState';
import { EmptyState } from '../../src/components/EmptyState';
import { SkeletonFeed } from '../../src/components/SkeletonCard';
import { FilterSheet, FilterState, EMPTY_FILTERS, hasActiveFilters } from '../../src/components/FilterSheet';
import { useAuthStore } from '../../src/stores/authStore';
import { AuthSheet } from '../../src/components/AuthSheet';
import { useDecisionSession } from '../../src/hooks/useDecisionSession';
import { DecisionReasonCode, DecisionRole, DecisionSessionCard } from '../../src/api/decisionSession';
import { foundationQueryKey, STALE_TIME } from '../../src/contracts/foundationGate';

const VIEWABILITY_CONFIG = { itemVisiblePercentThreshold: 50, minimumViewTime: 250 };
const DISCOVERY_LIMIT = 4;

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

type DiscoveryReason = 'taste_extension' | 'hole_in_wall' | 'from_craves' | 'discover_new';

interface DiscoverySection {
  reason: DiscoveryReason;
  title: string;
  subtitle: string;
  places: PlaceOut[];
}

type FeedRow =
  | { kind: 'decision'; card: DecisionSessionCard; position: number }
  | { kind: 'discovery_header'; section: DiscoverySection }
  | { kind: 'place'; place: PlaceOut; reason: DiscoveryReason; position: number };

function uniquePlaces(
  candidates: PlaceOut[],
  excluded: Set<string>,
  limit = DISCOVERY_LIMIT,
): PlaceOut[] {
  const result: PlaceOut[] = [];
  for (const place of candidates) {
    if (excluded.has(place.id)) continue;
    excluded.add(place.id);
    result.push(place);
    if (result.length >= limit) break;
  }
  return result;
}

export default function FeedScreen() {
  const router = useRouter();
  const prefetchPlace = usePrefetchPlace();
  const selectedCity = useCityStore((s) => s.selectedCity);
  const initCities = useCityStore((s) => s.initCities);
  const { saves, addSave, removeSave, isSaved } = useCravesStore();
  const toast = useToast((s) => s.show);
  const user = useAuthStore((s) => s.user);

  const userLocation = useLocation();
  const recommendationsQuery = useRecommendations(Boolean(user));
  const recommendations = recommendationsQuery.data ?? [];
  const decisionSession = useDecisionSession();
  const decisionCards = decisionSession.data?.cards ?? [];

  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const radiusMiles = 20;
  const [authVisible, setAuthVisible] = useState(false);
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
    isRefetchError,
    dataUpdatedAt,
    refetch,
  } = useInfiniteQuery({
    queryKey: foundationQueryKey({ scope: selectedCity ? 'city' : 'session', entity: 'feed', params: feedParams }),
    queryFn: ({ pageParam, signal }) =>
      fetchPlaces({
        ...feedParams,
        pagination: 'cursor',
        cursor: pageParam,
        signal,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    staleTime: STALE_TIME.normal,
  });

  const places = useMemo(() => {
    const seen = new Set<string>();
    const result: PlaceOut[] = [];
    for (const page of data?.pages ?? []) {
      for (const place of page.items) {
        if (seen.has(place.id)) continue;
        seen.add(place.id);
        result.push(place);
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
    for (const place of places) {
      for (const category of place.categories ?? []) names.add(category);
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
    void Promise.all([
      refetch(),
      decisionSession.refetch(),
      ...(user ? [recommendationsQuery.refetch()] : []),
    ]);
  };

  const handleEndReached = () => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage();
  };

  const filteredPlaces = useMemo(() => {
    if (!hasActiveFilters(filters)) return places;
    return places.filter((place) => {
      if (
        filters.priceTiers.length > 0 &&
        (place.price_tier == null || !filters.priceTiers.includes(place.price_tier))
      ) return false;
      if (
        filters.categories.length > 0 &&
        !place.categories.some((category) => filters.categories.includes(category))
      ) return false;
      return true;
    });
  }, [places, filters]);

  const discoverySections = useMemo<DiscoverySection[]>(() => {
    const excluded = new Set(decisionCards.map((card) => card.place.id));
    const sections: DiscoverySection[] = [];

    if (user && recommendations.length > 0) {
      const tasteExtension = uniquePlaces(recommendations, excluded);
      if (tasteExtension.length > 0) {
        sections.push({
          reason: 'taste_extension',
          title: 'MORE IN YOUR LANE',
          subtitle: 'Taste-based options beyond tonight’s three answers.',
          places: tasteExtension,
        });
      }
    }

    const holeInWall = uniquePlaces(
      filteredPlaces.filter((place) => getTierForPlace(place).key === 'gem'),
      excluded,
    );
    if (holeInWall.length > 0) {
      sections.push({
        reason: 'hole_in_wall',
        title: 'HOLE-IN-THE-WALL',
        subtitle: 'Strong local signal without turning popularity into the ranking.',
        places: holeInWall,
      });
    }

    const savedCandidates = saves.filter((saved) => !saved.visited);
    const fromCraves = uniquePlaces(savedCandidates, excluded);
    if (fromCraves.length > 0) {
      sections.push({
        reason: 'from_craves',
        title: 'FROM YOUR CRAVES',
        subtitle: 'Places you already wanted to try that still deserve a decision.',
        places: fromCraves,
      });
    }

    const discoveryTail = uniquePlaces(filteredPlaces, excluded, Number.POSITIVE_INFINITY);
    if (discoveryTail.length > 0) {
      sections.push({
        reason: 'discover_new',
        title: 'MORE TO DISCOVER',
        subtitle: 'The rest of today’s nearby options, with a real end to the list.',
        places: discoveryTail,
      });
    }

    return sections;
  }, [decisionCards, filteredPlaces, recommendations, saves, user]);

  const rows = useMemo<FeedRow[]>(() => {
    const result: FeedRow[] = decisionCards.map((card, position) => ({
      kind: 'decision',
      card,
      position,
    }));

    let discoveryPosition = 0;
    for (const section of discoverySections) {
      result.push({ kind: 'discovery_header', section });
      for (const place of section.places) {
        result.push({
          kind: 'place',
          place,
          reason: section.reason,
          position: discoveryPosition++,
        });
      }
    }
    return result;
  }, [decisionCards, discoverySections]);

  // An active filter can narrow the currently-loaded cursor pages down to
  // zero rows -- without this, that read as a genuine "no matches" dead
  // end: the FlashList below (the only thing wired to onEndReached) isn't
  // rendered when rows.length is 0, so nothing would ever trigger
  // fetchNextPage again even though hasNextPage may still be true and a
  // real match may simply be sitting on a page not fetched yet. Keeps
  // pulling the next page via the same cursor mechanism handleEndReached
  // already uses -- no page_size/query-key change, so no extra impression-
  // logging churn -- until a match appears or the feed genuinely runs out.
  const isCatchingUpForFilter = hasActiveFilters(filters) && rows.length === 0 && hasNextPage;
  useEffect(() => {
    if (isCatchingUpForFilter && !isFetchingNextPage) {
      void fetchNextPage();
    }
  }, [isCatchingUpForFilter, isFetchingNextPage, fetchNextPage]);

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
        const exposureKey = `feed:${row.reason}:${row.place.id}`;
        if (exposedKeysRef.current.has(exposureKey)) continue;
        exposedKeysRef.current.add(exposureKey);
        events.push({
          surface: 'feed',
          event_type: 'impression',
          place_id: row.place.id,
          position: row.position,
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

  const handleSave = async (
    place: PlaceOut,
    surface: 'feed' | 'decision_session',
    position: number,
    role?: DecisionRole,
  ) => {
    if (!user) {
      setAuthVisible(true);
      return;
    }

    const saveMeta = {
      surface,
      position,
      rank_percentile: place.rank_percentile,
      city_id: selectedCity?.id ?? null,
      // Wave 7 relationship hierarchy -- persists "why you saved this" on
      // the save itself (docs/CLAUDE_EXECUTION_BRIEF_WAVES_7_10_2026-09-08.md).
      // Only meaningful for a role-bearing Decision Session card, not the
      // plain Feed row.
      reason_role: role,
      reason_source: role ? ('decision_session' as const) : undefined,
    };

    if (isSaved(place.id)) {
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      const err = await removeSave(place.id, user.id, saveMeta);
      toast(err ?? 'Removed from Saves');
      return;
    }

    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    const err = await addSave(place, user.id, saveMeta);
    toast(err ?? 'Saved');
  };

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
          router.push(`/place/${card.place.id}?reason_role=${card.role}&reason_source=decision_session`);
        }}
        onPressIn={() => prefetchPlace(card.place.id)}
        onSave={() => handleSave(card.place, 'decision_session', position, card.role)}
        saved={isSaved(card.place.id)}
        style={styles.decisionCard}
      />
    </View>
  );

  const decisionHeader = (
    <View style={styles.decisionSectionHeader}>
      <Text style={styles.decisionEyebrow}>DECISION SESSION</Text>
      <Text style={styles.decisionHeading}>What should I eat?</Text>
      <Text style={styles.decisionSubheading}>
        {decisionSession.data?.degraded
          ? 'Confidence is lower right now, so these are the best answers CRAVE can support.'
          : 'Three distinct answers, kept small so you can actually decide.'}
      </Text>
      {decisionSession.isError ? (
        <TouchableOpacity
          style={styles.decisionRetry}
          onPress={() => void decisionSession.refetch()}
          accessibilityRole="button"
          accessibilityLabel="Retry Decision Session"
        >
          <Ionicons name="refresh" size={16} color={Colors.text} />
          <Text style={styles.decisionRetryText}>Decision Session unavailable. Retry</Text>
        </TouchableOpacity>
      ) : null}
      {recommendationsQuery.isError && user ? (
        <TouchableOpacity
          style={styles.decisionRetry}
          onPress={() => void recommendationsQuery.refetch()}
          accessibilityRole="button"
          accessibilityLabel="Retry personalized discovery"
        >
          <Ionicons name="refresh" size={16} color={Colors.text} />
          <Text style={styles.decisionRetryText}>Personalized discovery unavailable. Retry</Text>
        </TouchableOpacity>
      ) : null}
      {(isRefetchError || decisionSession.isRefetchError) && dataUpdatedAt > 0 ? (
        <Text style={styles.staleNotice} accessibilityRole="alert">
          Showing saved results from {new Date(dataUpdatedAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}.
        </Text>
      ) : null}
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
          accessibilityLabel="Filter discovery places"
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

      {!initialLoaded ? (
        <View style={styles.skeletonWrap}><SkeletonFeed count={4} /></View>
      ) : (
        <Animated.View style={[{ flex: 1 }, { opacity: feedOpacity }]}>
          {isError && decisionCards.length === 0 ? (
            <ErrorState message="Couldn't load places" onRetry={() => void refetch()} />
          ) : isCatchingUpForFilter ? (
            <View style={styles.skeletonWrap}><SkeletonFeed count={4} /></View>
          ) : rows.length === 0 ? (
            <View style={styles.emptyWrap}>
              {decisionHeader}
              <EmptyState
                icon="search-outline"
                title="No confident answer yet"
                body={selectedCity
                  ? 'Try a different city or use Search to tell CRAVE what you want.'
                  : 'Choose an area or use Search to tell CRAVE what you want.'}
              />
            </View>
          ) : (
            <FlashList
              data={rows}
              keyExtractor={(row) => {
                if (row.kind === 'place') return `discovery-${row.reason}-${row.place.id}`;
                if (row.kind === 'decision') return `decision-${row.card.role}-${row.card.place.id}`;
                return `discovery-header-${row.section.reason}`;
              }}
              getItemType={(row) => row.kind}
              renderItem={({ item: row }) => {
                if (row.kind === 'decision') return renderDecisionCard(row.card, row.position);

                if (row.kind === 'discovery_header') {
                  return (
                    <View style={styles.discoveryHeader}>
                      <Text style={styles.discoveryHeading}>{row.section.title}</Text>
                      <Text style={styles.discoverySubheading}>{row.section.subtitle}</Text>
                    </View>
                  );
                }

                return (
                  <View style={styles.rowSpacer}>
                    <PlaceCard
                      place={row.place}
                      onPress={() => {
                        logRecommendationEvent({
                          surface: 'feed',
                          event_type: 'click',
                          place_id: row.place.id,
                          position: row.position,
                          rank_percentile: row.place.rank_percentile,
                          city_id: selectedCity?.id ?? null,
                        });
                        router.push(`/place/${row.place.id}`);
                      }}
                      onPressIn={() => prefetchPlace(row.place.id)}
                      onSave={() => handleSave(row.place, 'feed', row.position)}
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
              ListHeaderComponent={decisionHeader}
              ListFooterComponent={
                isFetchingNextPage
                  ? <ActivityIndicator color={Colors.primary} style={styles.listFooter} />
                  : !hasNextPage
                    ? <Text style={styles.endState}>That’s everything new today.</Text>
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
  emptyWrap: { flex: 1, paddingHorizontal: Spacing.md },
  decisionSectionHeader: {
    paddingTop: Spacing.md,
    paddingBottom: Spacing.lg,
  },
  decisionEyebrow: {
    color: Colors.primary,
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1.6,
    marginBottom: Spacing.xs,
  },
  decisionHeading: {
    color: Colors.text,
    fontSize: 28,
    fontWeight: '900',
    letterSpacing: -0.5,
    marginBottom: Spacing.xs,
  },
  decisionSubheading: {
    color: Colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    maxWidth: 420,
  },
  decisionRetry: {
    minHeight: 44,
    marginTop: Spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  decisionRetryText: {
    color: Colors.text,
    fontSize: 13,
    fontWeight: '700',
  },
  staleNotice: {
    color: Colors.textSecondary,
    fontSize: 13,
    lineHeight: 18,
    marginTop: Spacing.sm,
  },
  decisionCard: { marginBottom: 0 },
  discoveryHeader: {
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  discoveryHeading: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '900',
    letterSpacing: 1.2,
  },
  discoverySubheading: {
    color: Colors.textSecondary,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 3,
  },
  listFooter: { margin: Spacing.lg },
  endState: {
    color: Colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
    paddingVertical: Spacing.xl,
  },
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
