import React, { useEffect, useMemo, useRef, useState } from 'react';
import { RefreshControl, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { FlashList, ViewToken } from '@shopify/flash-list';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { randomUUID } from 'expo-crypto';
import { useCityStore } from '../stores/cityStore';
import { usePrefetchPlace } from '../hooks/usePrefetchPlace';
import { searchPlaces } from '../api/search';
import { useLocationStatus } from '../hooks/useLocation';
import { PlaceOut } from '../api/places';
import type { SearchInterpretation } from '../api/search';
import { getTierForPlace } from '../utils/scoring';
import { logRecommendationEvent, logRecommendationEvents } from '../utils/recommendationEventQueue';
import { Colors, Radius, Spacing } from '../constants/colors';
import { PlaceCardCompact } from '../components/PlaceCardCompact';
import type { SearchReasonRole } from '../components/DecisionStrip';
import { CitySelectorStrip } from '../components/CitySelectorStrip';
import { SkeletonRowList } from '../components/SkeletonCard';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { FilterSheet, FilterState, EMPTY_FILTERS, hasActiveFilters } from '../components/FilterSheet';
import { useAuthStore } from '../stores/authStore';
import { useCravesStore } from '../stores/cravesStore';
import { useRecentSearchesStore } from '../stores/recentSearchesStore';
import { fetchMyRankings } from '../api/social';
import { SearchScope, useDiscoveryContextStore } from '../stores/discoveryContextStore';

function makeSearchSessionId(): string {
  return randomUUID();
}

/**
 * Search's Reason Block label (Search Screen Contract §6). Explains results
 * in their existing order -- it never reranks them. Evidence-based only:
 * derived from each place's own real catalog tier (the same signal already
 * shown via TierBadge/percentileCaption elsewhere), never a fabricated
 * personalized-fit claim.
 *
 * "Best match for you" is reserved for the single top-ranked result, and
 * only when the search didn't need to relax what the user actually asked
 * for -- claiming a top match after a compromise (e.g. a relaxed price
 * constraint) would overstate the evidence.
 */
function searchReasonForResult(
  place: PlaceOut,
  position: number,
  priceWasRelaxed: boolean,
): SearchReasonRole {
  const tier = getTierForPlace(place).key;
  if (position === 0 && !priceWasRelaxed && (tier === 'crave_pick' || tier === 'gem')) {
    return 'best_match';
  }
  if (tier === 'crave_pick' || tier === 'solid') {
    return 'safer_pick';
  }
  return 'worth_exploring';
}

/**
 * Zero-state's time-relevant intent shortcut (Search Screen Contract §5/§6).
 * Deliberately a plain time-of-day rule, not personalized or inferred from
 * any user data -- "the smallest honest implementation," not invented
 * backend intelligence. Each phrase is real interpretable intent (e.g.
 * "Quick lunch" matches the interpreter's own `quick` context phrase), not
 * decorative copy.
 */
export function intentShortcutForHour(hour: number): string {
  if (hour >= 5 && hour < 11) return 'Breakfast nearby';
  if (hour >= 11 && hour < 15) return 'Quick lunch';
  if (hour >= 15 && hour < 17) return 'Afternoon coffee';
  if (hour >= 17 && hour < 21) return 'Dinner tonight';
  return 'Late-night eats';
}

interface ZeroResultInfo {
  title: string;
  body: string;
  /** Present only when a specific, safe-to-relax constraint exists to
   * offer removing. Absent (not a fabricated fallback) when none does. */
  relaxKey?: string;
  relaxLabel?: string;
}

/**
 * Zero-result relaxation offer (Search Screen Contract §11). Names the
 * smallest specific relaxation the interpreted query can actually justify
 * -- never a generic "try broadening your search," and never a dietary/
 * allergy hard constraint (contract §9/§16). When no safe relaxation
 * exists, says so directly instead of implying one does.
 */
export function zeroResultInfo(
  interpretation: SearchInterpretation | undefined,
  priceWasRelaxed: boolean,
): ZeroResultInfo {
  if (!interpretation) {
    return { title: 'No results', body: 'Nothing matched right now.' };
  }

  if (interpretation.unsupported_hard_constraints.length > 0) {
    return {
      title: 'No results shown',
      body: "We can't verify this safely from what we know yet, so nothing is shown here -- that isn't something a different search would fix.",
    };
  }

  // required_categories are always the dietary/allergy phrases the
  // interpreter also records as hard_constraints (see query_interpreter.py)
  // -- never offered here. context entries (near_me/date_night/open_late/
  // quick) and an unrelaxed price tier are the only genuinely soft signals.
  const hardSet = new Set(interpretation.hard_constraints);
  const candidates: { key: string; label: string }[] = [];
  if (interpretation.price_tier != null && !priceWasRelaxed) {
    candidates.push({ key: 'price', label: `the ${'$'.repeat(interpretation.price_tier)} price filter` });
  }
  interpretation.context.forEach((key) => {
    if (!hardSet.has(key)) candidates.push({ key, label: key.replace(/_/g, ' ') });
  });

  if (candidates.length > 0) {
    const [target] = candidates;
    return {
      title: 'No results with these filters',
      body: `No matches with ${target.label}.`,
      relaxKey: target.key,
      relaxLabel: target.label,
    };
  }

  return {
    title: 'No results',
    body: `Nothing matched "${interpretation.lookup_query}" right now.`,
  };
}

const VIEWABILITY_CONFIG = { itemVisiblePercentThreshold: 50, minimumViewTime: 250 };
const DEFAULT_RESULT_LIMIT = 8;
const RESULT_STEP = 8;
const MAX_RESULT_LIMIT = 56;

// Matches the backend's own MAX_PAGE_SIZE (search.py) -- FilterSheet's
// price/category filters are applied client-side against whatever page
// was already fetched, so while a filter is active this requests the
// backend's full allowed page instead of the small Show-more-ratcheted
// window, so a real match outside that smaller window doesn't read as
// "no matches for these filters."
const SEARCH_MAX_PAGE_SIZE = 100;

// Backend enforces radius_miles only when lat/lng are also present (see
// search.py's effective_radius_miles) -- null here means "any distance,"
// the same as never sending the param at all.
const RADIUS_OPTIONS: { value: number | null; label: string }[] = [
  { value: null, label: 'Any distance' },
  { value: 1, label: '1 mi' },
  { value: 3, label: '3 mi' },
  { value: 10, label: '10 mi' },
];

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
  const recentQueries = useRecentSearchesStore((state) => state.queries);
  const addRecentQuery = useRecentSearchesStore((state) => state.addQuery);
  const intentShortcut = useMemo(() => intentShortcutForHour(new Date().getHours()), []);

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState<string | null>(null);
  const [scope, setScope] = useState<SearchScope>('all');
  const [resultLimit, setResultLimit] = useState(DEFAULT_RESULT_LIMIT);
  // Deliberately not reset on a new query alongside resultLimit/scope/
  // filters below -- a distance preference reads as "how far am I
  // willing to go today," not something tied to one specific search.
  const [radiusMiles, setRadiusMiles] = useState<number | null>(null);
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

  // Meaningless without a location to measure from -- same guard the
  // backend route itself applies (search.py's effective_radius_miles) --
  // so a stale radiusMiles picked before location resolved never gets
  // silently sent as if it meant something.
  const effectiveRadiusMiles = userLocation ? radiusMiles ?? undefined : undefined;

  const filtersActive = hasActiveFilters(filters);
  // See SEARCH_MAX_PAGE_SIZE's own comment -- resultLimit's Show-more
  // ratchet only matters for the unfiltered view; while a filter is
  // active this asks for everything the backend will hand back in one
  // page instead.
  const effectivePageSize = filtersActive ? SEARCH_MAX_PAGE_SIZE : resultLimit;

  const searchQuery = useQuery({
    queryKey: ['search', debouncedQuery, userLocation?.lat, userLocation?.lng, effectiveRadiusMiles, effectivePageSize],
    queryFn: ({ signal }) => searchPlaces({
      query: debouncedQuery,
      lat: userLocation?.lat,
      lng: userLocation?.lng,
      radius_miles: effectiveRadiusMiles,
      page_size: effectivePageSize,
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

  /** Zero-state shortcut tap (recent search or the time-relevant intent
   * shortcut) -- a deliberate, explicit search, so it searches immediately
   * rather than waiting out the normal debounce, and it's recorded like any
   * other explicit search. */
  const applyShortcut = (text: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    searchSessionIdRef.current = makeSearchSessionId();
    setQuery(text);
    setSubmittedQuery(null);
    setDebouncedQuery(text);
    addRecentQuery(text);
  };

  const priceWasRelaxed = Boolean(searchData?.relaxed_constraints.includes('price'));

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
                // A pending debounce from onChangeText must not fire after
                // this explicit submit already set debouncedQuery -- an
                // identical late setDebouncedQuery is at best redundant,
                // and firing after unmount is a real dangling-update bug.
                if (debounceRef.current) clearTimeout(debounceRef.current);
                setSubmittedQuery(submitted);
                setDebouncedQuery(submitted);
                addRecentQuery(submitted);
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
          {searchData.relaxed_constraints.includes('radius') && (
            <Text style={styles.relaxationText}>Nothing within {radiusMiles} mi — showing farther matches too.</Text>
          )}
        </View>
      )}

      {searched && userLocation && (
        <View style={styles.scopeRow}>
          {RADIUS_OPTIONS.map(({ value, label }) => (
            <TouchableOpacity
              key={label}
              style={[styles.scopeChip, radiusMiles === value && styles.scopeChipActive]}
              onPress={() => setRadiusMiles(value)}
              accessibilityRole="button"
              accessibilityLabel={`Distance: ${label}`}
              accessibilityState={{ selected: radiusMiles === value }}
            >
              <Text style={[styles.scopeText, radiusMiles === value && styles.scopeTextActive]}>{label}</Text>
            </TouchableOpacity>
          ))}
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
        <View style={styles.zeroState}>
          <Text style={styles.zeroStateTitle}>What are you craving?</Text>
          <TouchableOpacity
            style={styles.shortcutChip}
            onPress={() => applyShortcut(intentShortcut)}
            accessibilityRole="button"
            accessibilityLabel={`Search ${intentShortcut}`}
          >
            <Ionicons name="time-outline" size={14} color={Colors.primary} />
            <Text style={styles.shortcutText}>{intentShortcut}</Text>
          </TouchableOpacity>

          {recentQueries.length > 0 && (
            <>
              <Text style={styles.zeroStateSectionLabel}>RECENT SEARCHES</Text>
              <View style={styles.shortcutRow}>
                {recentQueries.map((recent) => (
                  <TouchableOpacity
                    key={recent}
                    style={styles.shortcutChip}
                    onPress={() => applyShortcut(recent)}
                    accessibilityRole="button"
                    accessibilityLabel={`Search ${recent} again`}
                  >
                    <Ionicons name="time-outline" size={14} color={Colors.textSecondary} />
                    <Text style={styles.shortcutText}>{recent}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </>
          )}

          <Text style={styles.zeroStateSectionLabel}>CITY</Text>
          <CitySelectorStrip />
        </View>
      )}
      {showBelowThreshold && <View style={styles.loadingRow}><Text style={styles.hintText}>Keep typing to search…</Text></View>}
      {showNoResults && (() => {
        const info = zeroResultInfo(searchData?.interpretation, priceWasRelaxed);
        return (
          <EmptyState
            icon="search-outline"
            title={info.title}
            body={info.body}
            ctaLabel={info.relaxKey ? `Remove ${info.relaxLabel}` : undefined}
            onCta={info.relaxKey ? () => removeInterpretedConstraint(info.relaxKey!) : undefined}
          />
        );
      })()}

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
          renderItem={({ item }) => {
            const position = results.findIndex((place) => place.id === item.id);
            const reason = searchReasonForResult(item, position, priceWasRelaxed);
            return (
              <View style={styles.rowSpacer}>
                <PlaceCardCompact
                  place={item}
                  searchReason={reason}
                  onPress={() => {
                    logRecommendationEvent({
                      surface: 'search',
                      event_type: 'click',
                      place_id: item.id,
                      position,
                      rank_percentile: item.rank_percentile,
                      query: debouncedQuery,
                      city_id: selectedCity?.id ?? null,
                      search_session_id: searchSessionIdRef.current,
                    });
                    router.push(
                      reason
                        ? `/place/${item.id}?reason_role=${reason}&reason_source=search`
                        : `/place/${item.id}`,
                    );
                  }}
                  onPressIn={() => prefetchPlace(item.id)}
                />
              </View>
            );
          }}
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
          ListFooterComponent={searchData && searchData.total > results.length && resultLimit < MAX_RESULT_LIMIT && !filtersActive ? (
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
  zeroState: { paddingHorizontal: Spacing.md, paddingTop: Spacing.sm, gap: Spacing.xs },
  zeroStateTitle: { color: Colors.text, fontSize: 17, fontWeight: '800', marginBottom: Spacing.xs },
  zeroStateSectionLabel: { color: Colors.textSecondary, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', marginTop: Spacing.sm, marginBottom: Spacing.xs },
  shortcutRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.xs },
  shortcutChip: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 44, paddingHorizontal: Spacing.md, borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, alignSelf: 'flex-start' },
  shortcutText: { color: Colors.text, fontSize: 13, fontWeight: '600' },
  interpretationPanel: { marginHorizontal: Spacing.md, marginBottom: Spacing.xs, padding: Spacing.sm, backgroundColor: Colors.surface, borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.border },
  interpretationTitle: { color: Colors.primary, fontSize: 10, fontWeight: '800', letterSpacing: 1.2 },
  interpretationQuery: { color: Colors.text, fontSize: 13, fontWeight: '700', marginTop: 4 },
  constraintRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.xs, marginTop: Spacing.xs },
  constraintChip: { minHeight: 36, justifyContent: 'center', paddingHorizontal: Spacing.sm, borderRadius: Radius.full, backgroundColor: Colors.surfaceElevated },
  constraintText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '700', textTransform: 'capitalize' },
  constraintWarning: { color: Colors.error, fontSize: 12, lineHeight: 17, marginTop: Spacing.xs },
  relaxationText: { color: Colors.textSecondary, fontSize: 12, lineHeight: 17, marginTop: Spacing.xs },
  scopeRow: { flexDirection: 'row', gap: Spacing.xs, paddingHorizontal: Spacing.md, paddingVertical: Spacing.xs },
  scopeChip: { minHeight: 44, justifyContent: 'center', paddingHorizontal: Spacing.md, borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.border },
  scopeChipActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  scopeText: { color: Colors.textSecondary, fontSize: 13, fontWeight: '700' },
  scopeTextActive: { color: Colors.background },
  resultsHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingBottom: Spacing.sm },
  resultCount: { color: Colors.textSecondary, fontSize: 11, fontWeight: '700', textTransform: 'uppercase' },
  mapLink: { color: Colors.primary, fontSize: 13, fontWeight: '800' },
  showMoreButton: { minHeight: 48, alignItems: 'center', justifyContent: 'center', marginTop: Spacing.sm, borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.primary },
  showMoreText: { color: Colors.primary, fontSize: 14, fontWeight: '800' },
});
