// app/(tabs)/search.tsx
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { FlashList, ViewToken } from '@shopify/flash-list';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useCityStore } from '../../src/stores/cityStore';
import { usePrefetchPlace } from '../../src/hooks/usePrefetchPlace';
import { searchPlaces } from '../../src/api/search';
import { useLocationStatus } from '../../src/hooks/useLocation';
import { PlaceOut } from '../../src/api/places';
import { useTrendingWithRefresh } from '../../src/hooks/useTrending';
import { logRecommendationEvent, logRecommendationEvents } from '../../src/utils/recommendationEventQueue';
import { Colors, Radius, Spacing } from '../../src/constants/colors';
import { PlaceCardCompact } from '../../src/components/PlaceCardCompact';
import { SkeletonRowList } from '../../src/components/SkeletonCard';
import { ErrorState } from '../../src/components/ErrorState';
import { EmptyState } from '../../src/components/EmptyState';
import { FilterSheet, FilterState, EMPTY_FILTERS, hasActiveFilters } from '../../src/components/FilterSheet';

// Same pattern as client.ts's requestId / recommendationEventQueue's
// module-level sessionId -- no external uuid dependency needed.
function _makeSearchSessionId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

// Item must be at least half on-screen, for at least 250ms, to count as
// actually seen -- a fling-scroll a card flashes through doesn't log an
// impression just because it technically entered the viewport.
const VIEWABILITY_CONFIG = { itemVisiblePercentThreshold: 50, minimumViewTime: 250 };

export default function SearchScreen() {
  const router = useRouter();
  const prefetchPlace = usePrefetchPlace();
  const selectedCity = useCityStore((s) => s.selectedCity);
  // useLocationStatus() (not the coords-or-null useLocation()) -- this
  // screen distinguishes "still resolving" from "denied/unavailable" in
  // its own copy below, which the collapsed coords-or-null contract
  // can't express.
  const locationState = useLocationStatus();
  const userLocation = locationState.coords;

  const [trending, trendingRefreshing, refreshTrending] = useTrendingWithRefresh();

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // handleChange below clears the *previous* timer before setting a new
  // one, but nothing previously cleared the pending timer on unmount --
  // navigating away within the 350ms debounce window (a real, plausible
  // user action, not just a test artifact) left a timer alive that would
  // fire setDebouncedQuery on an already-unmounted screen. Confirmed via
  // Jest's --detectOpenHandles: three leaked Timeout handles, all from
  // this exact setTimeout, were why the frontend test process needed
  // --forceExit to ever exit cleanly.
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // One search interaction session -- narrower than the app-launch
  // session recommendationEventQueue already tracks. Reminted whenever
  // a fresh query starts from an empty box (see handleChange below),
  // so a later analysis can group "query -> results shown -> selection"
  // into one arc without an idle-timeout state machine, and reformulation
  // (a new query replacing the previous one before any selection) is
  // fully derivable from consecutive logged queries sharing this id --
  // no separate "reformulated" event needed.
  const searchSessionIdRef = useRef(_makeSearchSessionId());
  // Place ids already logged as exposed for the *current* query -- a
  // viewability callback fires repeatedly as items scroll in and out, so
  // this is what keeps each result logged exactly once. Reset whenever
  // the query itself changes (a fresh query's results start unexposed
  // again, even if some of the same places happen to reappear).
  const exposedIdsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    exposedIdsRef.current = new Set();
  }, [debouncedQuery]);

  // Deliberately NOT scoped to selectedCity -- a search should find a
  // real match anywhere in the catalog, not just within whatever city
  // happens to be selected (live-reported bug: searching a real place's
  // name while "Alameda" was selected returned nothing, because the
  // match existed but was filtered out for being in a different city).
  // lat/lng (when available) drive proximity ranking instead, both at
  // the database level (search_query.py orders by distance so a real
  // nearby match is never crowded out of the fetch window by unrelated,
  // higher-rank_score places elsewhere) and in the final display order.
  const { data: searchData, isLoading: searchLoading, isError: searchError, refetch: refetchSearch, isRefetching: searchRefetching } = useQuery({
    queryKey: ['search', debouncedQuery, userLocation?.lat, userLocation?.lng],
    queryFn: ({ signal }) => searchPlaces({
      query: debouncedQuery,
      lat: userLocation?.lat,
      lng: userLocation?.lng,
      page_size: 30,
    }, signal),
    enabled: debouncedQuery.length >= 2,
    staleTime: 60 * 1000,  // 1 min
  });

  const results = searchData ?? [];
  const searched = debouncedQuery.length >= 2 && !searchLoading && searchData !== undefined;

  // Recommendation Ledger: log an impression only once a result is
  // actually *exposed* (scrolled into view), not the instant the backend
  // returns it ("retrieved" -- results the user may never scroll to
  // would previously be logged as impressions the moment they arrived).
  // Kept as a ref-stable wrapper since FlashList's onViewableItemsChanged
  // identity must not change across renders, while the logic inside
  // still needs each render's current results/debouncedQuery/selectedCity.
  const handleViewableItemsChangedRef = useRef<(info: { viewableItems: ViewToken<PlaceOut>[] }) => void>(() => {});
  handleViewableItemsChangedRef.current = (info) => {
    const newlyExposed = info.viewableItems.filter(
      (v) => v.isViewable && v.item && !exposedIdsRef.current.has(v.item.id),
    );
    if (newlyExposed.length === 0) return;
    newlyExposed.forEach((v) => exposedIdsRef.current.add(v.item.id));

    logRecommendationEvents(
      newlyExposed.map((v) => ({
        surface: 'search',
        event_type: 'impression',
        place_id: v.item.id,
        // Position within the full, unfiltered `results` -- same
        // convention the click handler below already uses -- not
        // FlashList's own index, which is local to whatever filtered
        // view is currently rendered.
        position: results.findIndex((r) => r.id === v.item.id),
        rank_percentile: v.item.rank_percentile,
        query: debouncedQuery,
        city_id: selectedCity?.id ?? null,
        search_session_id: searchSessionIdRef.current,
      })),
    );
  };
  const onViewableItemsChanged = useRef((info: { viewableItems: ViewToken<PlaceOut>[] }) =>
    handleViewableItemsChangedRef.current(info)
  ).current;

  if (__DEV__ && searchData) {
    console.log('[SEARCH] RENDER_INPUT', { query: debouncedQuery, count: results.length, sample: results[0] ? { id: results[0].id, category: results[0].category } : null });
  }

  // Derived from the current results, not a global catalog-wide fetch --
  // same fix as Feed's filter chips (see index.tsx): every chip shown is
  // guaranteed to have a real match in what's already on screen.
  const availableCategories = useMemo(() => {
    const names = new Set<string>();
    for (const p of results) {
      for (const c of p.categories ?? []) names.add(c);
    }
    return Array.from(names);
  }, [results]);

  // A view-level narrowing of what's already fetched, not a new query --
  // impressions above are still logged against the full `results` (what
  // the search actually returned), matching Feed's identical precedent.
  const filteredResults = useMemo(() => {
    if (!hasActiveFilters(filters)) return results;
    return results.filter((p) => {
      if (filters.priceTiers.length > 0 && (p.price_tier == null || !filters.priceTiers.includes(p.price_tier))) return false;
      if (filters.categories.length > 0 && !p.categories.some((c) => filters.categories.includes(c))) return false;
      return true;
    });
  }, [results, filters]);

  const handleChange = (text: string) => {
    // A fresh query starting from an empty box begins a new search
    // interaction session -- see searchSessionIdRef's own comment.
    if (query.length === 0 && text.trim().length > 0) {
      searchSessionIdRef.current = _makeSearchSessionId();
    }
    setQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!text.trim()) {
      setDebouncedQuery('');
      return;
    }
    debounceRef.current = setTimeout(() => setDebouncedQuery(text), 350);
  };

  const handleClear = () => {
    // A pending debounce timer from text typed just before this tap would
    // otherwise still fire 350ms later and resurrect the query this
    // button just cleared -- setDebouncedQuery(stale text) overwriting
    // the '' set right below it.
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setQuery('');
    setDebouncedQuery('');
  };

  const showTrending = !searched && !searchLoading && query.length === 0;
  const showNoResults = searched && results.length === 0 && !searchError;
  // Distinct from showNoResults -- the search itself found real matches,
  // the active filters just narrowed them to zero. Same failure mode
  // Feed's filter chips could hit before being scoped to loaded data;
  // here it's still possible since a filter picked from an earlier,
  // larger result set can outlive a narrower new query's results.
  const showNoFilterMatches = searched && results.length > 0 && filteredResults.length === 0;
  // Below the 2-char query threshold, nothing else here renders anything —
  // no trending (query isn't empty), no results/no-results state (search
  // never actually fires). Without this, that gap between "empty" and
  // "searched" reads as a blank, broken screen instead of "keep typing."
  const showBelowThreshold = query.length > 0 && query.length < 2;

  return (
    <View style={styles.container}>
      {/* Search bar */}
      <View style={styles.bar}>
        <View style={styles.barRow}>
          <View style={[styles.inputRow, styles.inputRowFlex]}>
            <Ionicons name="search" size={16} color={Colors.textSecondary} style={styles.searchIcon} />
            <TextInput
              style={styles.input}
              placeholder="Search places, cuisines…"
              placeholderTextColor={Colors.textSecondary}
              value={query}
              onChangeText={handleChange}
              returnKeyType="search"
              onSubmitEditing={() => setDebouncedQuery(query)}
              autoCorrect={false}
              accessibilityLabel="Search input"
            />
            {query.length > 0 && (
              <TouchableOpacity
                onPress={handleClear}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                accessibilityLabel="Clear search"
                accessibilityRole="button"
              >
                <Ionicons name="close-circle" size={18} color={Colors.textSecondary} />
              </TouchableOpacity>
            )}
          </View>
          {searched && results.length > 0 && (
            <TouchableOpacity
              style={styles.filterBtn}
              onPress={() => setFilterVisible(true)}
              accessibilityLabel="Filter results"
              accessibilityRole="button"
            >
              <Ionicons name="options-outline" size={20} color={hasActiveFilters(filters) ? Colors.primary : Colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
        <Text style={styles.cityContext}>
          {locationState.status === 'granted'
            ? 'Searching everywhere, nearest first'
            : locationState.status === 'resolving'
              // Previously identical to the denied/unavailable copy below
              // -- falsely implied "no location" during what's usually a
              // brief, self-resolving wait, rather than an honest pending
              // state. The search itself still runs unaffected either
              // way; only this line's wording depended on the collapsed
              // coords-or-null contract not being able to tell "still
              // resolving" apart from a terminal no-location state.
              ? 'Searching everywhere — finding your location…'
              : 'Searching everywhere'}
        </Text>
      </View>

      {/* Loading -- matches search results' actual PlaceCardCompact row
          shape, same skeleton treatment as Feed/Craves/Profile/Leaderboard/
          Friends Feed. Search was still a bare spinner, the one list
          screen in the app not using it. */}
      {searchLoading && (
        <View style={styles.list}>
          <SkeletonRowList count={5} />
        </View>
      )}

      {/* Error */}
      {searchError && !searchLoading && (
        <ErrorState message="Couldn't search right now." onRetry={() => refetchSearch()} />
      )}

      {/* Trending empty state */}
      {showTrending && (
        <FlashList
          data={trending}
          keyExtractor={(p) => p.id}
          renderItem={({ item }) => (
            <View style={styles.rowSpacer}>
              <PlaceCardCompact
                place={item}
                onPress={() => router.push(`/place/${item.id}`)}
                onPressIn={() => prefetchPlace(item.id)}
              />
            </View>
          )}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={trendingRefreshing}
              onRefresh={refreshTrending}
              tintColor={Colors.primary}
            />
          }
          ListHeaderComponent={
            trending.length > 0 ? (
              <>
                <Text style={styles.browseIntro}>
                  Discover what's moving in {selectedCity?.name ?? 'your city'}
                </Text>
                <Text style={styles.sectionLabel}>TRENDING NOW</Text>
              </>
            ) : null
          }
          ListEmptyComponent={
            // Without this, an empty `trending` (the default "Near Me" state
            // with no city selected never fetches trending at all — see
            // useTrending.ts) rendered a totally blank area here,
            // indistinguishable from a stuck load.
            <View style={styles.loadingRow}>
              <Ionicons name="flame-outline" size={22} color={Colors.textSecondary} />
              <Text style={[styles.hintText, styles.emptyTrendingText]}>
                Pick a city to see what's trending, or start typing to search everywhere.
              </Text>
            </View>
          }
        />
      )}

      {/* Below the query-length threshold */}
      {showBelowThreshold && (
        <View style={styles.loadingRow}>
          <Text style={styles.hintText}>Keep typing to search…</Text>
        </View>
      )}

      {/* No results */}
      {showNoResults && (
        <EmptyState
          icon="search-outline"
          title="No results"
          body="Nothing matched. Try broader terms."
        />
      )}

      {/* Real matches exist, the active filters just narrowed them out --
          distinct from showNoResults above (nothing matched the query at
          all). "Clear filters" is faster than backtracking into the
          sheet to find what's active. */}
      {showNoFilterMatches && (
        <EmptyState
          icon="options-outline"
          title="No matches for these filters"
          body="Try clearing a filter to see more results."
          ctaLabel="Clear filters"
          onCta={() => setFilters(EMPTY_FILTERS)}
        />
      )}

      {/* Results */}
      {!showTrending && !showNoResults && !showNoFilterMatches && !searchError && filteredResults.length > 0 && (
        <FlashList
          data={filteredResults}
          keyExtractor={(p) => p.id}
          viewabilityConfig={VIEWABILITY_CONFIG}
          onViewableItemsChanged={onViewableItemsChanged}
          renderItem={({ item }) => (
            <View style={styles.rowSpacer}>
              <PlaceCardCompact
                place={item}
                onPress={() => {
                  logRecommendationEvent({
                    surface: 'search',
                    event_type: 'click',
                    place_id: item.id,
                    // Position within the originally logged impression
                    // batch (the full, unfiltered `results`), not this
                    // filtered view's local index -- a click must tie
                    // back to the "this was shown" event it corresponds
                    // to, same principle as Craves/Map's position fix.
                    position: results.findIndex((r) => r.id === item.id),
                    rank_percentile: item.rank_percentile,
                    query: debouncedQuery,
                    city_id: selectedCity?.id ?? null,
                    search_session_id: searchSessionIdRef.current,
                  });
                  router.push(`/place/${item.id}`);
                }}
                onPressIn={() => prefetchPlace(item.id)}
              />
            </View>
          )}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={searchRefetching}
              onRefresh={() => refetchSearch()}
              tintColor={Colors.primary}
            />
          }
          ListHeaderComponent={
            <Text style={styles.resultCount}>
              {filteredResults.length} result{filteredResults.length !== 1 ? 's' : ''}
              {filteredResults.length !== results.length ? ` of ${results.length}` : ''}
            </Text>
          }
        />
      )}

      <FilterSheet
        visible={filterVisible}
        onClose={() => setFilterVisible(false)}
        filters={filters}
        onChange={setFilters}
        availableCategories={availableCategories}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  bar: { padding: Spacing.md, paddingBottom: Spacing.xs, gap: Spacing.xs },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  inputRowFlex: { flex: 1 },
  filterBtn: { padding: Spacing.sm, minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.md,
    paddingVertical: 10,
    gap: Spacing.sm,
    minHeight: 46,
  },
  searchIcon: { marginRight: 2 },
  input: { flex: 1, color: Colors.text, fontSize: 15 },
  cityContext: { color: Colors.textSecondary, fontSize: 12, fontWeight: '500', paddingLeft: Spacing.xs },
  loadingRow: { paddingVertical: 20, alignItems: 'center', gap: Spacing.sm },
  hintText: { color: Colors.textSecondary, fontSize: 13 },
  emptyTrendingText: { textAlign: 'center', paddingHorizontal: Spacing.xl },
  // FlashList's contentContainerStyle doesn't reliably support `gap`
  // (unlike FlatList) -- https://github.com/Shopify/flash-list/issues/2097 --
  // so inter-row spacing is applied per-row via rowSpacer below instead.
  list: { padding: Spacing.md, paddingBottom: Spacing.xxl },
  rowSpacer: { marginBottom: Spacing.sm },
  browseIntro: {
    fontSize: 22,
    fontWeight: '800',
    color: Colors.text,
    paddingBottom: Spacing.lg,
  },
  sectionLabel: {
    color: Colors.primary,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.5,
    paddingBottom: Spacing.sm,
  },
  resultCount: { color: Colors.textSecondary, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', paddingBottom: Spacing.sm },
});
