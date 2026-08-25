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
import { FlashList } from '@shopify/flash-list';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useInfiniteQuery } from '@tanstack/react-query';
import { fetchPlaces, PlaceOut } from '../../src/api/places';
import { fetchCategories, CategoryOut } from '../../src/api/categories';
import { useCityStore } from '../../src/stores/cityStore';
import { useCravesStore } from '../../src/stores/cravesStore';
import { useToast } from '../../src/hooks/useToast';
import { useTrending } from '../../src/hooks/useTrending';
import { useRecommendations } from '../../src/hooks/useRecommendations';
import { useLocation } from '../../src/hooks/useLocation';
import { usePrefetchPlace } from '../../src/hooks/usePrefetchPlace';
import { Colors, Spacing, Radius } from '../../src/constants/colors';
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

// Radius is fixed for now — UI controls removed until we know what's
// actually useful to users (was: Walking 0.5mi / Biking 2mi / Close 5mi /
// Worth It 20mi / Road Trip 50mi presets). Revisit once we have signal.

// Hidden for now (2026-08-25), deliberately: with too little real usage
// data yet, both strips are misleading rather than useful.
// "Recommended for You" (useRecommendations -> get_recommendations)
// falls back to generic catalog-wide top-rated places for any user
// with no ranked places of their own yet -- indistinguishable from
// "Trending" in practice, and mislabeled as personalized when it isn't.
// "Trending" (useTrending) is driven by save/interaction counts that are
// still thin enough to be closer to noise than signal at this stage.
// Showing confident-looking suggestions backed by weak data actively
// hurts trust more than having no suggestion at all. Turn this back on
// once there's a real per-user ranking history (for "Recommended for
// You") and enough save volume for "Trending" to reflect actual
// behavior rather than a handful of test taps -- see
// CRAVE_REMAINING_WORK.md for the decision record.
const SHOW_FEED_DISCOVERY_STRIPS = false;

type FeedRow =
  | { kind: 'header'; tierKey: TierKey; count: number }
  | { kind: 'place'; place: PlaceOut };

function buildFeedRows(places: PlaceOut[]): FeedRow[] {
  const buckets: Record<TierKey, PlaceOut[]> = {
    crave_pick: [],
    gem: [],
    solid: [],
    new: [],
  };
  for (const p of places) {
    buckets[getTierForPlace(p).key].push(p);
  }
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
  const trending = useTrending();
  const recommendations = useRecommendations();

  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const radiusMiles = 20;
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
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
    isLoading,
    isError,
    refetch,
  } = useInfiniteQuery({
    queryKey: ['feed', feedParams],
    queryFn: ({ pageParam = 1 }) =>
      fetchPlaces({ ...feedParams, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((sum, p) => sum + p.items.length, 0);
      return loaded < lastPage.total ? allPages.length + 1 : undefined;
    },
    staleTime: 2 * 60 * 1000,
  });

  // Pages are fetched by 1-indexed page number against an offset/limit
  // backend query ordered by rank_score, not a stable cursor — live-
  // confirmed via a real "duplicate key" crash that the discovery
  // pipeline inserting new places between page fetches (it runs on a
  // 5-minute interval, and now processes a growing OSM/Overture backlog
  // faster than before this session) shifts every subsequent page's
  // offset window, so the same place can land in both an already-loaded
  // page and the next one fetched. De-duping here fixes the actual user-
  // visible crash regardless of the underlying pagination-shift cause —
  // a real cursor-based fix is a much larger backend change than
  // warranted for this.
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
  const initialLoaded = data !== undefined;

  if (__DEV__ && data) {
    const lastPage = data.pages[data.pages.length - 1];
    console.log('[FEED] PLACES_LOADED', { page: lastPage?.page, count: places.length, total, sample: places[0] ? { id: places[0].id, category: places[0].category, categories: places[0].categories } : null });
  }

  // Recommendation Ledger: log one impression per place the first time
  // its page actually arrives. Keyed on page count (not `places.length`
  // or `data` itself) so a re-render that doesn't add a new page -- e.g.
  // toggling a filter, which only changes `filteredPlaces`/`rows` below
  // -- never re-logs impressions for pages already counted. Reset
  // whenever the underlying query itself changes (new city/location),
  // since that's a new, unrelated set of impressions.
  const loggedFeedPageCountRef = useRef(0);
  useEffect(() => {
    loggedFeedPageCountRef.current = 0;
  }, [selectedCity?.id, userLocation?.lat, userLocation?.lng, radiusMiles]);
  useEffect(() => {
    const pages = data?.pages ?? [];
    if (pages.length <= loggedFeedPageCountRef.current) return;
    let position = pages
      .slice(0, loggedFeedPageCountRef.current)
      .reduce((sum, p) => sum + p.items.length, 0);
    const events: Parameters<typeof logRecommendationEvents>[0] = [];
    for (const page of pages.slice(loggedFeedPageCountRef.current)) {
      for (const p of page.items) {
        events.push({
          surface: 'feed',
          event_type: 'impression',
          place_id: p.id,
          position,
          rank_percentile: p.rank_percentile,
          city_id: selectedCity?.id ?? null,
        });
        position += 1;
      }
    }
    loggedFeedPageCountRef.current = pages.length;
    if (events.length > 0) logRecommendationEvents(events);
  }, [data?.pages.length, selectedCity?.id]);

  useEffect(() => {
    fetchCategories()
      .then((cats) => {
        if (__DEV__) console.log('[FEED] CATEGORIES_LOADED', { count: cats.length, names: cats.map((c) => c.name) });
        setAvailableCategories(cats.map((c) => c.name));
      })
      // Filter options are non-critical — a failure here shouldn't be an
      // unhandled rejection, it should just leave the filter list empty.
      .catch(() => setAvailableCategories([]));
  }, []);

  // Always populate the city list on mount — it's never persisted (only
  // selectedCity is), and initCities() no longer overrides an existing
  // selection, so this is safe to run unconditionally. Previously gated on
  // "no city selected", which meant anyone with a city already saved from
  // a prior session would never get a populated list, hiding the whole
  // CitySelectorStrip (including "Near Me") for good.
  useEffect(() => {
    initCities();
  }, []);

  // Fade in feed when data arrives
  useEffect(() => {
    if (initialLoaded && !isError) {
      Animated.timing(feedOpacity, {
        toValue: 1,
        duration: 350,
        useNativeDriver: true,
      }).start();
    }
  }, [initialLoaded, isError]);

  // Reset fade when query key changes (city/location/radius change)
  useEffect(() => {
    feedOpacity.setValue(0);
  }, [selectedCity?.id, userLocation?.lat, userLocation?.lng, radiusMiles]);

  const handleRefresh = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    refetch();
  };
  const handleEndReached = () => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  };

  const filteredPlaces = useMemo(() => {
    if (!hasActiveFilters(filters)) return places;
    return places.filter(p => {
      if (filters.priceTiers.length > 0 && (p.price_tier == null || !filters.priceTiers.includes(p.price_tier))) return false;
      if (filters.categories.length > 0 && !p.categories.some((c) => filters.categories.includes(c))) return false;
      return true;
    });
  }, [places, filters]);

  // Previously recomputed on every render (re-bucketing every place into
  // tiers) even when triggered by unrelated state like filterVisible or
  // authVisible toggling -- filteredPlaces just above already gets this
  // memoization, buildFeedRows didn't.
  const rows = useMemo(() => buildFeedRows(filteredPlaces), [filteredPlaces]);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.wordmark}>CRAVE</Text>
        <View style={styles.spacer} />
        <TouchableOpacity
          style={styles.filterBtn}
          onPress={() => {
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
            setFilterVisible(true);
          }}
          accessibilityLabel="Filter places"
          accessibilityRole="button"
        >
          <Ionicons name="options-outline" size={20} color={hasActiveFilters(filters) ? Colors.primary : Colors.textSecondary} />
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
            <ErrorState message="Couldn't load places" onRetry={() => refetch()} />
          ) : rows.length === 0 ? (
            <EmptyState
              icon="search-outline"
              title="Nothing here yet"
              body={selectedCity ? "Try selecting a different city" : "No places found"}
            />
          ) : (
            <FlashList
              data={rows}
              keyExtractor={(row, i) => row.kind === 'place' ? row.place.id : `header-${i}`}
              getItemType={(row) => row.kind}
              renderItem={({ item: row }) => {
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
                return (
                  <View style={styles.rowSpacer}>
                    <PlaceCard
                      place={row.place}
                      onPress={() => {
                        logRecommendationEvent({
                          surface: 'feed',
                          event_type: 'click',
                          place_id: row.place.id,
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
                        if (isSaved(row.place.id)) {
                          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
                          const err = await removeSave(row.place.id, user.id);
                          toast(err ?? 'Removed from Saves');
                        } else {
                          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
                          const err = await addSave(row.place, user.id);
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
              refreshControl={
                <RefreshControl
                  refreshing={isFetching && !isFetchingNextPage && initialLoaded}
                  onRefresh={handleRefresh}
                  tintColor={Colors.primary}
                />
              }
              ListFooterComponent={
                isFetchingNextPage ? <ActivityIndicator color={Colors.primary} style={styles.listFooter} /> : null
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
  // FlashList's contentContainerStyle doesn't reliably support `gap`
  // (unlike FlatList) -- https://github.com/Shopify/flash-list/issues/2097 --
  // so inter-row spacing is applied per-row via rowSpacer below instead.
  list: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.xxl },
  rowSpacer: { marginBottom: Spacing.md },
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
  filterBtn: { padding: Spacing.sm, minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  spacer: { flex: 1 },
});
