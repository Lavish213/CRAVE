// app/(tabs)/search.tsx
import React, { useEffect, useRef, useState } from 'react';
import {
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useCityStore } from '../../src/stores/cityStore';
import { searchPlaces } from '../../src/api/search';
import { useLocation } from '../../src/hooks/useLocation';
import { PlaceOut } from '../../src/api/places';
import { useTrendingWithRefresh } from '../../src/hooks/useTrending';
import { Colors, Radius, Spacing } from '../../src/constants/colors';
import { PlaceCardCompact } from '../../src/components/PlaceCardCompact';
import { SkeletonRowList } from '../../src/components/SkeletonCard';
import { ErrorState } from '../../src/components/ErrorState';
import { EmptyState } from '../../src/components/EmptyState';

export default function SearchScreen() {
  const router = useRouter();
  const selectedCity = useCityStore((s) => s.selectedCity);
  const userLocation = useLocation();

  const [trending, trendingRefreshing, refreshTrending] = useTrendingWithRefresh();

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    queryFn: () => searchPlaces({
      query: debouncedQuery,
      lat: userLocation?.lat,
      lng: userLocation?.lng,
      page_size: 30,
    }),
    enabled: debouncedQuery.length >= 2,
    staleTime: 60 * 1000,  // 1 min
  });

  const results = searchData ?? [];
  const searched = debouncedQuery.length >= 2 && !searchLoading && searchData !== undefined;

  if (__DEV__ && searchData) {
    console.log('[SEARCH] RENDER_INPUT', { query: debouncedQuery, count: results.length, sample: results[0] ? { id: results[0].id, category: results[0].category } : null });
  }

  const handleChange = (text: string) => {
    setQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!text.trim()) {
      setDebouncedQuery('');
      return;
    }
    debounceRef.current = setTimeout(() => setDebouncedQuery(text), 350);
  };

  const handleClear = () => {
    setQuery('');
    setDebouncedQuery('');
  };

  const showTrending = !searched && !searchLoading && query.length === 0;
  const showNoResults = searched && results.length === 0 && !searchError;
  // Below the 2-char query threshold, nothing else here renders anything —
  // no trending (query isn't empty), no results/no-results state (search
  // never actually fires). Without this, that gap between "empty" and
  // "searched" reads as a blank, broken screen instead of "keep typing."
  const showBelowThreshold = query.length > 0 && query.length < 2;

  return (
    <View style={styles.container}>
      {/* Search bar */}
      <View style={styles.bar}>
        <View style={styles.inputRow}>
          <Ionicons name="search" size={16} color={Colors.textMuted} style={styles.searchIcon} />
          <TextInput
            style={styles.input}
            placeholder="Search places, cuisines…"
            placeholderTextColor={Colors.textMuted}
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
              <Ionicons name="close-circle" size={18} color={Colors.textMuted} />
            </TouchableOpacity>
          )}
        </View>
        <Text style={styles.cityContext}>
          {userLocation ? 'Searching everywhere, nearest first' : 'Searching everywhere'}
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
        <ErrorState message="Couldn't search right now." onRetry={() => setDebouncedQuery(query)} />
      )}

      {/* Trending empty state */}
      {showTrending && (
        <FlashList
          data={trending}
          keyExtractor={(p) => p.id}
          renderItem={({ item }) => (
            <View style={styles.rowSpacer}>
              <PlaceCardCompact place={item} onPress={() => router.push(`/place/${item.id}`)} />
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
              <Ionicons name="flame-outline" size={22} color={Colors.textMuted} />
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

      {/* Results */}
      {!showTrending && !showNoResults && !searchError && results.length > 0 && (
        <FlashList
          data={results}
          keyExtractor={(p) => p.id}
          renderItem={({ item }) => (
            <View style={styles.rowSpacer}>
              <PlaceCardCompact place={item} onPress={() => router.push(`/place/${item.id}`)} />
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
            <Text style={styles.resultCount}>{results.length} result{results.length !== 1 ? 's' : ''}</Text>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  bar: { padding: Spacing.md, paddingBottom: Spacing.xs, gap: Spacing.xs },
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
  cityContext: { color: Colors.textMuted, fontSize: 12, fontWeight: '500', paddingLeft: Spacing.xs },
  loadingRow: { paddingVertical: 20, alignItems: 'center', gap: Spacing.sm },
  hintText: { color: Colors.textMuted, fontSize: 13 },
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
  resultCount: { color: Colors.textMuted, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', paddingBottom: Spacing.sm },
});
