import React, { useEffect, useMemo, useRef, useState } from 'react';
import { RefreshControl, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { FlashList, ViewToken } from '@shopify/flash-list';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useCityStore } from '../stores/cityStore';
import { usePrefetchPlace } from '../hooks/usePrefetchPlace';
import { searchPlaces } from '../api/search';
import { useLocationStatus } from '../hooks/useLocation';
import { PlaceOut } from '../api/places';
import { logRecommendationEvent, logRecommendationEvents } from '../utils/recommendationEventQueue';
import { Colors, Radius, Spacing } from '../constants/colors';
import { PlaceCardCompact } from '../components/PlaceCardCompact';
import { SkeletonRowList } from '../components/SkeletonCard';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { FilterSheet, FilterState, EMPTY_FILTERS, hasActiveFilters } from '../components/FilterSheet';
import { useAuthStore } from '../stores/authStore';
import { useCravesStore } from '../stores/cravesStore';
import { fetchMyRankings } from '../api/social';
import { SearchScope, useDiscoveryContextStore } from '../stores/discoveryContextStore';

function makeSearchSessionId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

const VIEWABILITY_CONFIG = { itemVisiblePercentThreshold: 50, minimumViewTime: 250 };
const DEFAULT_RESULT_LIMIT = 8;
const RESULT_STEP = 8;
const MAX_RESULT_LIMIT = 56;

const CONSTRAINT_PATTERNS: Record<string, RegExp> = {
  price: /\b(?:cheap|budget|inexpensive|splurge|expensive|fine\s+dining)\b/gi,
  near_me: /\bnear\s+me\b/gi,
  date_night: /\bdate\s+night\b/gi,
  open_late: /\bopen\s+late\b/gi,
  quick: /\bquick\s+(?:bite|lunch|dinner)\b/gi,
  Vegan: /\bvegan\b/gi,
  Vegetarian: /\bvegetarian\b/gi,
  Halal: /\bhalal\b/gi,
  Kosher: /\bkosher\b/gi,
  'Gluten Free': /\bgluten[-\s]?free\b/gi,
};

export default function SearchScreen() {
  const router = useRouter();
  const prefetchPlace = usePrefetchPlace();
  const user = useAuthStore((state) => state.user);
  const saves = useCravesStore((state) => state.saves);
  const selectedCity = useCityStore((state) => state.selectedCity);
  const setSearchMapHandoff = useDiscoveryContextStore((state) => state.setSearchMapHandoff);
  const locationState = useLocationStatus();
  const userLocation = locationState.coords;

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState<string | null>(null);
  const [scope, setScope] = useState<SearchScope>('all');
  const [resultLimit, setResultLimit] = useState(DEFAULT_RESULT_LIMIT);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [filterVisible, setFilterVisible] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchSessionIdRef = useRef(makeSearchSessionId());
  const exposedIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  useEffect(() => {
    exposedIdsRef.current = new Set();
    setResultLimit(DEFAULT_RESULT_LIMIT);
    setScope('all');
    setFilters(EMPTY_FILTERS);
  }, [debouncedQuery]);

  const searchQuery = useQuery({
    queryKey: ['search', debouncedQuery, userLocation?.lat, userLocation?.lng, resultLimit],
    queryFn: ({ signal }) => searchPlaces({
      query: debouncedQuery,
      lat: userLocation?.lat,
      lng: userLocation?.lng,
      page_size: resultLimit,
    }, signal),
    enabled: debouncedQuery.length >= 2,
    staleTime: 60_000,
  });

  const rankingQuery = useQuery({
    queryKey: ['myRankings', user?.id ?? null, 'search-scope'],
    queryFn: fetchMyRankings,
    enabled: Boolean(user) && scope === 'ranked',
    staleTime: 60_000,
  });

  const searchData = searchQuery.data;
  const results = searchData?.items ?? [];
  const rankings = rankingQuery.data ?? [];
  const searched = debouncedQuery.length >= 2 && !searchQuery.isLoading && searchData !== undefined;
  const rankedScopeLoading = scope === 'ranked' && rankingQuery.isLoading;
  const rankedScopeError = scope === 'ranked' && rankingQuery.isError;

  useEffect(() => {
    if (submittedQuery && submittedQuery === debouncedQuery && searchData?.exact_match_id) {
      setSubmittedQuery(null);
      router.push(`/place/${searchData.exact_match_id}`);
    }
  }, [debouncedQuery, router, searchData?.exact_match_id, submittedQuery]);

  const handleViewableItemsChangedRef = useRef<(info: { viewableItems: ViewToken<PlaceOut>[] }) => void>(() => {});
  handleViewableItemsChangedRef.current = (info) => {
    const newlyExposed = info.viewableItems.filter(
      (viewToken) => viewToken.isViewable && viewToken.item && !exposedIdsRef.current.has(viewToken.item.id),
    );
    if (newlyExposed.length === 0) return;
    newlyExposed.forEach((viewToken) => exposedIdsRef.current.add(viewToken.item.id));
    logRecommendationEvents(newlyExposed.map((viewToken) => ({
      surface: 'search',
      event_type: 'impression',
      place_id: viewToken.item.id,
      position: results.findIndex((place) => place.id === viewToken.item.id),
      rank_percentile: viewToken.item.rank_percentile,
      query: debouncedQuery,
      city_id: selectedCity?.id ?? null,
      search_session_id: searchSessionIdRef.current,
    })));
  };
  const onViewableItemsChanged = useRef((info: { viewableItems: ViewToken<PlaceOut>[] }) => {
    handleViewableItemsChangedRef.current(info);
  }).current;

  const availableCategories = useMemo(() => {
    const names = new Set<string>();
    results.forEach((place) => place.categories?.forEach((category) => names.add(category)));
    return Array.from(names);
  }, [results]);

  const filteredResults = useMemo(() => {
    const savedIds = new Set(saves.map((place) => place.id));
    const rankedIds = new Set(rankings.map((ranking) => ranking.place_id));
    return results.filter((place) => {
      if (scope === 'craves' && !savedIds.has(place.id)) return false;
      if (scope === 'ranked' && !rankedIds.has(place.id)) return false;
      if (filters.priceTiers.length > 0 && (place.price_tier == null || !filters.priceTiers.includes(place.price_tier))) return false;
      if (filters.categories.length > 0 && !place.categories.some((category) => filters.categories.includes(category))) return false;
      return true;
    });
  }, [filters, rankings, results, saves, scope]);

  const handleChange = (text: string) => {
    if (query.length === 0 && text.trim().length > 0) searchSessionIdRef.current = makeSearchSessionId();
    setQuery(text);
    setSubmittedQuery(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!text.trim()) {
      setDebouncedQuery('');
      return;
    }
    debounceRef.current = setTimeout(() => setDebouncedQuery(text.trim()), 350);
  };

  const handleClear = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setQuery('');
    setDebouncedQuery('');
    setSubmittedQuery(null);
  };

  const removeInterpretedConstraint = (key: string) => {
    const pattern = CONSTRAINT_PATTERNS[key];
    if (!pattern) return;
    handleChange(query.replace(pattern, ' ').replace(/\s+/g, ' ').trim());
  };

  const showZeroState = query.length === 0 && !searchQuery.isLoading;
  const showBelowThreshold = query.length > 0 && query.length < 2;
  const showNoResults = searched && results.length === 0 && !searchQuery.isError;
  const showNoFilterMatches = searched && results.length > 0 && filteredResults.length === 0 && !rankedScopeLoading && !rankedScopeError;
  const canRenderResults = !showZeroState && !showNoResults && !showNoFilterMatches && !searchQuery.isError && !rankedScopeLoading && !rankedScopeError && filteredResults.length > 0;

  return (
    <View style={styles.container}>
      <View style={styles.bar}>
        <View style={styles.barRow}>
          <View style={[styles.inputRow, styles.inputRowFlex]}>
            <Ionicons name="search" size={16} color={Colors.textSecondary} />
            <TextInput
              style={styles.input}
              placeholder="Search places, cuisines…"
              placeholderTextColor={Colors.textSecondary}
              value={query}
              onChangeText={handleChange}
              returnKeyType="search"
              onSubmitEditing={() => {
                const submitted = query.trim();
                if (!submitted) return;
                setSubmittedQuery(submitted);
                setDebouncedQuery(submitted);
              }}
              autoCorrect={false}
              accessibilityLabel="Search input"
            />
            {query.length > 0 && (
              <TouchableOpacity onPress={handleClear} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }} accessibilityLabel="Clear search" accessibilityRole="button">
                <Ionicons name="close-circle" size={18} color={Colors.textSecondary} />
              </TouchableOpacity>
            )}
          </View>
          {searched && results.length > 0 && (
            <TouchableOpacity style={styles.filterBtn} onPress={() => setFilterVisible(true)} accessibilityLabel="Filter results" accessibilityRole="button">
              <Ionicons name="options-outline" size={20} color={hasActiveFilters(filters) ? Colors.primary : Colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
        <Text style={styles.cityContext}>
          {locationState.status === 'granted'
            ? 'Searching everywhere, nearest first'
            : locationState.status === 'resolving'
              ? 'Searching everywhere — finding your location…'
              : 'Searching everywhere'}
        </Text>
      </View>

      {searched && searchData?.interpretation && (
        <View style={styles.interpretationPanel}>
          <Text style={styles.interpretationTitle}>{searchData.interpretation.uncertain ? 'CHECK THIS SEARCH' : 'UNDERSTOOD'}</Text>
          <Text style={styles.interpretationQuery}>Searching for {searchData.interpretation.lookup_query}</Text>
          <View style={styles.constraintRow}>
            {searchData.interpretation.price_tier != null && (
              <TouchableOpacity style={styles.constraintChip} onPress={() => removeInterpretedConstraint('price')} accessibilityLabel="Remove price constraint">
                <Text style={styles.constraintText}>{'$'.repeat(searchData.interpretation.price_tier)} ×</Text>
              </TouchableOpacity>
            )}
            {[...searchData.interpretation.required_categories, ...searchData.interpretation.context].map((key) => (
              <TouchableOpacity key={key} style={styles.constraintChip} onPress={() => removeInterpretedConstraint(key)} accessibilityLabel={`Remove ${key.replace('_', ' ')} constraint`}>
                <Text style={styles.constraintText}>{key.replace('_', ' ')} ×</Text>
              </TouchableOpacity>
            ))}
          </View>
          {searchData.interpretation.unsupported_hard_constraints.length > 0 && (
            <Text style={styles.constraintWarning}>We can’t verify this allergy safely yet. No results were shown.</Text>
          )}
          {searchData.relaxed_constraints.includes('price') && (
            <Text style={styles.relaxationText}>No exact budget matches — showing broader prices. Dietary constraints stayed enforced.</Text>
          )}
        </View>
      )}

      {searched && user && (
        <View style={styles.scopeRow}>
          {(['all', 'craves', 'ranked'] as SearchScope[]).map((value) => (
            <TouchableOpacity
              key={value}
              style={[styles.scopeChip, scope === value && styles.scopeChipActive]}
              onPress={() => {
                setScope(value);
                if (value !== 'all') setResultLimit(MAX_RESULT_LIMIT);
              }}
              accessibilityRole="button"
              accessibilityState={{ selected: scope === value }}
            >
              <Text style={[styles.scopeText, scope === value && styles.scopeTextActive]}>{value === 'all' ? 'All' : value === 'craves' ? 'Craves' : 'Ranked'}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {searchQuery.isLoading && <View style={styles.list}><SkeletonRowList count={5} /></View>}
      {searchQuery.isError && !searchQuery.isLoading && <ErrorState message="Couldn't search right now." onRetry={() => searchQuery.refetch()} />}

      {showZeroState && (
        <EmptyState
          icon="search-outline"
          title="What are you craving?"
          body="Search a place, cuisine, dish, or intent like “quick ramen nearby.”"
        />
      )}
      {showBelowThreshold && <View style={styles.loadingRow}><Text style={styles.hintText}>Keep typing to search…</Text></View>}
      {showNoResults && <EmptyState icon="search-outline" title="No results" body="Nothing matched. Try broader terms." />}

      {rankedScopeLoading && <View style={styles.list}><SkeletonRowList count={4} /></View>}
      {rankedScopeError && (
        <ErrorState message="Couldn't load your ranked places." onRetry={() => rankingQuery.refetch()} />
      )}

      {showNoFilterMatches && (
        <EmptyState
          icon="options-outline"
          title="No matches for these filters"
          body="Try clearing a filter to see more results."
          ctaLabel="Clear filters"
          onCta={() => {
            setFilters(EMPTY_FILTERS);
            if (scope !== 'all') setScope('all');
          }}
        />
      )}

      {canRenderResults && (
        <FlashList
          data={filteredResults}
          keyExtractor={(place) => place.id}
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
                    position: results.findIndex((place) => place.id === item.id),
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
          refreshControl={<RefreshControl refreshing={searchQuery.isRefetching} onRefresh={() => searchQuery.refetch()} tintColor={Colors.primary} />}
          ListHeaderComponent={(
            <View style={styles.resultsHeader}>
              <Text style={styles.resultCount}>{filteredResults.length} result{filteredResults.length !== 1 ? 's' : ''}{filteredResults.length !== results.length ? ` of ${results.length}` : ''}</Text>
              <TouchableOpacity
                onPress={() => {
                  if (!searchData) return;
                  setSearchMapHandoff({
                    query: debouncedQuery,
                    searchSessionId: searchSessionIdRef.current,
                    interpretation: searchData.interpretation,
                    items: filteredResults,
                    scope,
                  });
                  router.push('/(tabs)/map');
                }}
                accessibilityRole="button"
                accessibilityLabel="Show these search results on map"
              >
                <Text style={styles.mapLink}>Map these results</Text>
              </TouchableOpacity>
            </View>
          )}
          ListFooterComponent={searchData && searchData.total > results.length && resultLimit < MAX_RESULT_LIMIT ? (
            <TouchableOpacity style={styles.showMoreButton} onPress={() => setResultLimit((value) => Math.min(MAX_RESULT_LIMIT, value + RESULT_STEP))} accessibilityRole="button">
              <Text style={styles.showMoreText}>Show more</Text>
            </TouchableOpacity>
          ) : null}
        />
      )}

      <FilterSheet visible={filterVisible} onClose={() => setFilterVisible(false)} filters={filters} onChange={setFilters} availableCategories={availableCategories} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  bar: { padding: Spacing.md, paddingBottom: Spacing.xs, gap: Spacing.xs },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  inputRowFlex: { flex: 1 },
  filterBtn: { padding: Spacing.sm, minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  inputRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.border, paddingHorizontal: Spacing.md, paddingVertical: 10, gap: Spacing.sm, minHeight: 46 },
  input: { flex: 1, color: Colors.text, fontSize: 15 },
  cityContext: { color: Colors.textSecondary, fontSize: 12, fontWeight: '500', paddingLeft: Spacing.xs },
  list: { padding: Spacing.md, paddingBottom: Spacing.xxl },
  rowSpacer: { marginBottom: Spacing.sm },
  loadingRow: { paddingVertical: 20, alignItems: 'center', gap: Spacing.sm },
  hintText: { color: Colors.textSecondary, fontSize: 13 },
  interpretationPanel: { marginHorizontal: Spacing.md, marginBottom: Spacing.xs, padding: Spacing.sm, backgroundColor: Colors.surface, borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.border },
  interpretationTitle: { color: Colors.primary, fontSize: 10, fontWeight: '800', letterSpacing: 1.2 },
  interpretationQuery: { color: Colors.text, fontSize: 13, fontWeight: '700', marginTop: 4 },
  constraintRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.xs, marginTop: Spacing.xs },
  constraintChip: { minHeight: 36, justifyContent: 'center', paddingHorizontal: Spacing.sm, borderRadius: Radius.full, backgroundColor: Colors.surfaceElevated },
  constraintText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '700', textTransform: 'capitalize' },
  constraintWarning: { color: Colors.error, fontSize: 12, lineHeight: 17, marginTop: Spacing.xs },
  relaxationText: { color: Colors.textSecondary, fontSize: 12, lineHeight: 17, marginTop: Spacing.xs },
  scopeRow: { flexDirection: 'row', gap: Spacing.xs, paddingHorizontal: Spacing.md, paddingVertical: Spacing.xs },
  scopeChip: { minHeight: 40, justifyContent: 'center', paddingHorizontal: Spacing.md, borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.border },
  scopeChipActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  scopeText: { color: Colors.textSecondary, fontSize: 13, fontWeight: '700' },
  scopeTextActive: { color: Colors.background },
  resultsHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingBottom: Spacing.sm },
  resultCount: { color: Colors.textSecondary, fontSize: 11, fontWeight: '700', textTransform: 'uppercase' },
  mapLink: { color: Colors.primary, fontSize: 13, fontWeight: '800' },
  showMoreButton: { minHeight: 48, alignItems: 'center', justifyContent: 'center', marginTop: Spacing.sm, borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.primary },
  showMoreText: { color: Colors.primary, fontSize: 14, fontWeight: '800' },
});
