import React, { useEffect, useMemo, useRef, useState } from 'react';
import { RefreshControl, StyleSheet, View } from 'react-native';
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
import { CitySelectorStrip } from '../components/CitySelectorStrip';
import { SkeletonRowList } from '../components/SkeletonCard';
import { ErrorState } from '../components/ErrorState';
import { FilterSheet, FilterState, EMPTY_FILTERS, hasActiveFilters } from '../components/FilterSheet';
import { useAuthStore } from '../stores/authStore';
import { useCravesStore } from '../stores/cravesStore';
import { useRecentSearchesStore } from '../stores/recentSearchesStore';
import { fetchMyRankings } from '../api/social';
import { SearchScope, useDiscoveryContextStore } from '../stores/discoveryContextStore';
import type { SearchReasonRole } from '../components/DecisionStrip';
import {
  ConstraintToken,
  DecisionRecovery,
  InterpretationLine,
  PlaceResultHero,
  PlaceResultSupporting,
  type ReasonKind,
} from '../ui-v2/components';
import {
  CraveButton,
  CraveIconButton,
  CraveInput,
  CravePressable,
  CraveText,
} from '../ui-v2/primitives';
import { uiColors, uiRadius, uiSpace } from '../ui-v2/tokens';

function makeSearchSessionId(): string {
  return randomUUID();
}

/**
 * Search's Reason Block label (Search Screen Contract §6). Explains results
 * in their existing order -- it never reranks them. Evidence-based only:
 * derived from each place's own real catalog tier (the same signal already
 * shown via TierBadge/percentileCaption elsewhere), never a fabricated
 * personalized-fit claim.
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

function reasonKindForSearchRole(role: SearchReasonRole): ReasonKind {
  if (role === 'best_match') return 'bestMatch';
  if (role === 'safer_pick') return 'saferPick';
  return 'worthExploring';
}

/**
 * Zero-state's time-relevant intent shortcut (Search Screen Contract §5/§6).
 * Deliberately a plain time-of-day rule, not personalized or inferred from
 * any user data.
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
  relaxKey?: string;
  relaxLabel?: string;
}

/**
 * Zero-result relaxation offer (Search Screen Contract §11). Names the
 * smallest specific relaxation the interpreted query can actually justify
 * and never offers a dietary/allergy hard constraint.
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
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [filterVisible, setFilterVisible] = useState(false);
  const [acceptedPriceRelaxation, setAcceptedPriceRelaxation] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<React.ElementRef<typeof CraveInput>>(null);
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
    setAcceptedPriceRelaxation(false);
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
  const showPreferredRelaxation = searched && results.length > 0 && priceWasRelaxed && !acceptedPriceRelaxation;
  const canRenderResults = !showZeroState
    && !showNoResults
    && !showNoFilterMatches
    && !showPreferredRelaxation
    && !searchQuery.isError
    && !rankedScopeLoading
    && !rankedScopeError
    && filteredResults.length > 0;

  const openResult = (item: PlaceOut, position: number, reason: SearchReasonRole) => {
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
    router.push(`/place/${item.id}?reason_role=${reason}&reason_source=search`);
  };

  const mapCurrentResults = () => {
    if (!searchData) return;
    setSearchMapHandoff({
      query: debouncedQuery,
      searchSessionId: searchSessionIdRef.current,
      interpretation: searchData.interpretation,
      items: filteredResults,
      scope,
    });
    router.push('/(tabs)/map');
  };

  return (
    <View style={styles.container}>
      <View style={styles.bar}>
        <View style={styles.barRow}>
          <CraveInput
            ref={inputRef}
            containerStyle={styles.inputFlex}
            leading={<Ionicons name="search" size={18} color={uiColors.text.secondary} />}
            trailing={query.length > 0 ? (
              <CraveIconButton
                accessibilityLabel="Clear search"
                icon={<Ionicons name="close-circle" size={20} color={uiColors.text.secondary} />}
                onPress={handleClear}
              />
            ) : undefined}
            placeholder="Search places, cuisines…"
            value={query}
            onChangeText={handleChange}
            returnKeyType="search"
            onSubmitEditing={() => {
              const submitted = query.trim();
              if (!submitted) return;
              if (debounceRef.current) clearTimeout(debounceRef.current);
              setSubmittedQuery(submitted);
              setDebouncedQuery(submitted);
              addRecentQuery(submitted);
            }}
            autoCorrect={false}
            accessibilityLabel="Search input"
          />
          {searched && results.length > 0 ? (
            <CraveIconButton
              accessibilityLabel="Filter results"
              selected={hasActiveFilters(filters)}
              icon={<Ionicons name="options-outline" size={21} color={hasActiveFilters(filters) ? uiColors.accent.selected : uiColors.text.secondary} />}
              onPress={() => setFilterVisible(true)}
            />
          ) : null}
        </View>
        <CraveText role="caption" tone="secondary">
          {locationState.status === 'granted'
            ? 'Searching everywhere, nearest first'
            : locationState.status === 'resolving'
              ? 'Searching everywhere — finding your location…'
              : 'Searching everywhere'}
        </CraveText>
      </View>

      {searched && searchData?.interpretation ? (
        <View style={styles.interpretationPanel}>
          <InterpretationLine query={searchData.interpretation.lookup_query} uncertain={searchData.interpretation.uncertain} />
          <View style={styles.constraintRow}>
            {searchData.interpretation.price_tier != null ? (
              <ConstraintToken
                label={'$'.repeat(searchData.interpretation.price_tier)}
                kind={priceWasRelaxed ? 'relaxed' : 'preferred'}
                onRemove={() => removeInterpretedConstraint('price')}
              />
            ) : null}
            {searchData.interpretation.required_categories.map((key) => (
              <ConstraintToken key={`required:${key}`} label={key.replace(/_/g, ' ')} kind="protected" onRemove={() => removeInterpretedConstraint(key)} />
            ))}
            {searchData.interpretation.context.map((key) => (
              <ConstraintToken key={`context:${key}`} label={key.replace(/_/g, ' ')} kind="preferred" onRemove={() => removeInterpretedConstraint(key)} />
            ))}
          </View>
          {searchData.interpretation.unsupported_hard_constraints.length > 0 ? (
            <CraveText role="caption" tone="destructive">We can’t verify this allergy safely yet. No results were shown.</CraveText>
          ) : null}
          {priceWasRelaxed && acceptedPriceRelaxation ? (
            <CraveText role="caption" tone="uncertain">Showing broader prices. Protected dietary constraints stayed enforced.</CraveText>
          ) : null}
        </View>
      ) : null}

      {searched && user ? (
        <View style={styles.scopeRow}>
          {(['all', 'craves', 'ranked'] as SearchScope[]).map((value) => {
            const selected = scope === value;
            const label = value === 'all' ? 'All' : value === 'craves' ? 'Craves' : 'Ranked';
            return (
              <CravePressable
                key={value}
                onPress={() => {
                  setScope(value);
                  if (value !== 'all') setResultLimit(MAX_RESULT_LIMIT);
                }}
                accessibilityLabel={`Search ${label}`}
                accessibilityState={{ selected }}
                style={[styles.scopeChip, selected ? styles.scopeChipActive : null]}
              >
                <CraveText role="caption" tone={selected ? 'brand' : 'secondary'}>{label}</CraveText>
              </CravePressable>
            );
          })}
        </View>
      ) : null}

      {searchQuery.isLoading ? <View style={styles.list}><SkeletonRowList count={5} /></View> : null}
      {searchQuery.isError && !searchQuery.isLoading ? <ErrorState message="Couldn't search right now." onRetry={() => searchQuery.refetch()} /> : null}

      {showZeroState ? (
        <View style={styles.zeroState}>
          <CraveText role="headline">What are you craving?</CraveText>
          <CravePressable
            style={styles.shortcutChip}
            onPress={() => applyShortcut(intentShortcut)}
            accessibilityLabel={`Search ${intentShortcut}`}
          >
            <Ionicons name="time-outline" size={16} color={uiColors.accent.brand} />
            <CraveText role="caption">{intentShortcut}</CraveText>
          </CravePressable>

          {recentQueries.length > 0 ? (
            <>
              <CraveText role="micro" tone="secondary" style={styles.sectionLabel}>RECENT SEARCHES</CraveText>
              <View style={styles.shortcutRow}>
                {recentQueries.map((recent) => (
                  <CravePressable
                    key={recent}
                    style={styles.shortcutChip}
                    onPress={() => applyShortcut(recent)}
                    accessibilityLabel={`Search ${recent} again`}
                  >
                    <Ionicons name="time-outline" size={16} color={uiColors.text.secondary} />
                    <CraveText role="caption">{recent}</CraveText>
                  </CravePressable>
                ))}
              </View>
            </>
          ) : null}

          <CraveText role="micro" tone="secondary" style={styles.sectionLabel}>CITY</CraveText>
          <CitySelectorStrip />
        </View>
      ) : null}

      {showBelowThreshold ? (
        <View style={styles.loadingRow}>
          <CraveText role="caption" tone="secondary">Keep typing to search…</CraveText>
        </View>
      ) : null}

      {showNoResults ? (() => {
        const info = zeroResultInfo(searchData?.interpretation, priceWasRelaxed);
        const unsupported = Boolean(searchData?.interpretation.unsupported_hard_constraints.length);
        return (
          <View style={styles.recoveryWrap}>
            <DecisionRecovery
              kind={unsupported ? 'requiredZero' : 'generic'}
              protectedConstraint={unsupported ? searchData?.interpretation.unsupported_hard_constraints[0] : undefined}
              title={info.title}
              body={info.body}
              primaryLabel={info.relaxKey ? `Remove ${info.relaxLabel}` : undefined}
              onPrimary={info.relaxKey ? () => removeInterpretedConstraint(info.relaxKey!) : undefined}
              secondaryLabel="Edit search"
              onSecondary={() => inputRef.current?.focus()}
            />
          </View>
        );
      })() : null}

      {showPreferredRelaxation ? (
        <View style={styles.recoveryWrap}>
          <DecisionRecovery
            kind="preferredNoExact"
            title="No exact budget match"
            body="CRAVE found options at broader prices. Protected dietary constraints stayed enforced."
            primaryLabel="See broader prices"
            onPrimary={() => setAcceptedPriceRelaxation(true)}
            secondaryLabel="Edit search"
            onSecondary={() => inputRef.current?.focus()}
          />
        </View>
      ) : null}

      {rankedScopeLoading ? <View style={styles.list}><SkeletonRowList count={4} /></View> : null}
      {rankedScopeError ? <ErrorState message="Couldn't load your ranked places." onRetry={() => rankingQuery.refetch()} /> : null}

      {showNoFilterMatches ? (
        <View style={styles.recoveryWrap}>
          <DecisionRecovery
            kind="generic"
            title="No matches for these filters"
            body="The search itself still has results. Clear the view filters to see them."
            primaryLabel="Clear filters"
            onPrimary={() => {
              setFilters(EMPTY_FILTERS);
              if (scope !== 'all') setScope('all');
            }}
            secondaryLabel="Edit search"
            onSecondary={() => inputRef.current?.focus()}
          />
        </View>
      ) : null}

      {canRenderResults ? (
        <FlashList
          data={filteredResults}
          keyExtractor={(place) => place.id}
          viewabilityConfig={VIEWABILITY_CONFIG}
          onViewableItemsChanged={onViewableItemsChanged}
          renderItem={({ item, index }) => {
            const position = results.findIndex((place) => place.id === item.id);
            const reason = searchReasonForResult(item, position, priceWasRelaxed);
            const commonProps = {
              place: item,
              reasonKind: reasonKindForSearchRole(reason),
              onPress: () => openResult(item, position, reason),
              onPressIn: () => prefetchPlace(item.id),
            };
            return (
              <View style={styles.rowSpacer}>
                {index === 0 ? <PlaceResultHero {...commonProps} /> : <PlaceResultSupporting {...commonProps} />}
              </View>
            );
          }}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={searchQuery.isRefetching} onRefresh={() => searchQuery.refetch()} tintColor={uiColors.accent.brand} />}
          ListHeaderComponent={(
            <View style={styles.resultsHeader}>
              <View style={styles.resultsHeaderCopy}>
                <CraveText role="micro" tone="secondary">
                  {filteredResults.length} result{filteredResults.length !== 1 ? 's' : ''}{filteredResults.length !== results.length ? ` of ${results.length}` : ''}
                </CraveText>
                <CraveText role="caption" tone="secondary">Best current matches first. More stays bounded.</CraveText>
              </View>
              <CraveButton label="Map" variant="ghost" onPress={mapCurrentResults} accessibilityLabel="Show these search results on map" />
            </View>
          )}
          ListFooterComponent={searchData && searchData.total > results.length && resultLimit < MAX_RESULT_LIMIT ? (
            <CraveButton
              label="Show more"
              variant="secondary"
              onPress={() => setResultLimit((value) => Math.min(MAX_RESULT_LIMIT, value + RESULT_STEP))}
              style={styles.showMoreButton}
            />
          ) : null}
        />
      ) : null}

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
  container: {
    flex: 1,
    backgroundColor: uiColors.surface.canvas,
  },
  bar: {
    paddingHorizontal: uiSpace.screenGutter,
    paddingTop: uiSpace.md,
    paddingBottom: uiSpace.xs,
    gap: uiSpace.xs,
  },
  barRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: uiSpace.sm,
  },
  inputFlex: {
    flex: 1,
  },
  list: {
    padding: uiSpace.screenGutter,
    paddingBottom: uiSpace.xxl,
  },
  rowSpacer: {
    marginBottom: uiSpace.md,
  },
  loadingRow: {
    paddingVertical: uiSpace.xl,
    alignItems: 'center',
  },
  zeroState: {
    paddingHorizontal: uiSpace.screenGutter,
    paddingTop: uiSpace.lg,
    gap: uiSpace.md,
  },
  sectionLabel: {
    marginTop: uiSpace.sm,
  },
  shortcutRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: uiSpace.sm,
  },
  shortcutChip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: uiSpace.sm,
    paddingHorizontal: uiSpace.md,
    borderRadius: uiRadius.pill,
    borderWidth: 1,
    borderColor: uiColors.border.subtle,
    backgroundColor: uiColors.surface.primary,
  },
  interpretationPanel: {
    marginHorizontal: uiSpace.screenGutter,
    marginBottom: uiSpace.xs,
    padding: uiSpace.md,
    gap: uiSpace.sm,
    backgroundColor: uiColors.surface.primary,
    borderRadius: uiRadius.card,
    borderWidth: 1,
    borderColor: uiColors.border.subtle,
  },
  constraintRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: uiSpace.sm,
  },
  scopeRow: {
    flexDirection: 'row',
    gap: uiSpace.sm,
    paddingHorizontal: uiSpace.screenGutter,
    paddingVertical: uiSpace.xs,
  },
  scopeChip: {
    paddingHorizontal: uiSpace.md,
    borderRadius: uiRadius.pill,
    borderWidth: 1,
    borderColor: uiColors.border.subtle,
    alignItems: 'center',
  },
  scopeChipActive: {
    backgroundColor: uiColors.surface.selected,
    borderColor: uiColors.border.selected,
  },
  recoveryWrap: {
    padding: uiSpace.screenGutter,
  },
  resultsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: uiSpace.md,
    paddingBottom: uiSpace.md,
  },
  resultsHeaderCopy: {
    flex: 1,
    gap: uiSpace.xs,
  },
  showMoreButton: {
    marginTop: uiSpace.sm,
  },
});
