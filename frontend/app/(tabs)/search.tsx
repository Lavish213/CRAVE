// app/(tabs)/search.tsx
import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useCityStore } from '../../src/stores/cityStore';
import { searchPlaces } from '../../src/api/search';
import { useLocation } from '../../src/hooks/useLocation';
import { PlaceOut } from '../../src/api/places';
import { useTrending } from '../../src/hooks/useTrending';
import { Colors, Spacing } from '../../src/constants/colors';
import { PlaceCardCompact } from '../../src/components/PlaceCardCompact';
import { ErrorState } from '../../src/components/ErrorState';
import { EmptyState } from '../../src/components/EmptyState';

export default function SearchScreen() {
  const router = useRouter();
  const selectedCity = useCityStore((s) => s.selectedCity);
  const userLocation = useLocation();

  const trending = useTrending();

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { data: searchData, isLoading: searchLoading, isError: searchError } = useQuery({
    queryKey: ['search', debouncedQuery, selectedCity?.id, userLocation],
    queryFn: () => searchPlaces({
      query: debouncedQuery,
      city_id: selectedCity?.id,
      lat: userLocation?.lat,
      lng: userLocation?.lng,
      limit: 30,
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
          {selectedCity ? `Searching in ${selectedCity.name}` : 'Searching everywhere'}
        </Text>
      </View>

      {/* Loading */}
      {searchLoading && (
        <View style={styles.loadingRow}>
          <ActivityIndicator color={Colors.primary} size="small" />
        </View>
      )}

      {/* Error */}
      {searchError && !searchLoading && (
        <ErrorState message="Search failed" onRetry={() => setDebouncedQuery(query)} />
      )}

      {/* Trending empty state */}
      {showTrending && (
        <FlatList
          data={trending}
          keyExtractor={(p) => p.id}
          renderItem={({ item }) => (
            <PlaceCardCompact place={item} onPress={() => router.push(`/place/${item.id}`)} />
          )}
          contentContainerStyle={styles.list}
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
        />
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
        <FlatList
          data={results}
          keyExtractor={(p) => p.id}
          renderItem={({ item }) => (
            <PlaceCardCompact place={item} onPress={() => router.push(`/place/${item.id}`)} />
          )}
          contentContainerStyle={styles.list}
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
  bar: { padding: 12, paddingBottom: 4, gap: 4 },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
    minHeight: 46,
  },
  searchIcon: { marginRight: 2 },
  input: { flex: 1, color: Colors.text, fontSize: 15 },
  cityContext: { color: Colors.textMuted, fontSize: 12, fontWeight: '500', paddingLeft: 4 },
  loadingRow: { paddingVertical: 20, alignItems: 'center' },
  list: { padding: 12, gap: 8, paddingBottom: 32 },
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
