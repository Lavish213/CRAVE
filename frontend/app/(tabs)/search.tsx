// app/(tabs)/search.tsx
import React, { useCallback, useRef, useState } from 'react';
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
import { useCityStore } from '../../src/stores/cityStore';
import { searchPlaces } from '../../src/api/search';
import { PlaceOut } from '../../src/api/places';
import { useTrending } from '../../src/hooks/useTrending';
import { Colors } from '../../src/constants/colors';
import { PlaceCardCompact } from '../../src/components/PlaceCardCompact';
import { ErrorState } from '../../src/components/ErrorState';
import { EmptyState } from '../../src/components/EmptyState';

export default function SearchScreen() {
  const router = useRouter();
  const selectedCity = useCityStore((s) => s.selectedCity);

  const trending = useTrending();

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PlaceOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [searched, setSearched] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim() || !selectedCity) {
      setResults([]);
      setSearched(false);
      return;
    }
    setLoading(true);
    setError(false);
    try {
      const data = await searchPlaces({ q, city_id: selectedCity.id, limit: 30 });
      setResults(data);
      setSearched(true);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [selectedCity]);

  const handleChange = (text: string) => {
    setQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(text), 350);
  };

  const handleClear = () => {
    setQuery('');
    setResults([]);
    setSearched(false);
    setError(false);
  };

  const showTrending = !searched && !loading && query.length === 0;
  const showNoResults = searched && !loading && results.length === 0 && !error;

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
            onSubmitEditing={() => doSearch(query)}
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
        {selectedCity && (
          <Text style={styles.cityContext}>Searching in {selectedCity.name}</Text>
        )}
      </View>

      {/* Loading */}
      {loading && (
        <View style={styles.loadingRow}>
          <ActivityIndicator color={Colors.primary} size="small" />
        </View>
      )}

      {/* Error */}
      {error && !loading && (
        <ErrorState message="Search failed" onRetry={() => doSearch(query)} />
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
            trending.length > 0 ? <Text style={styles.sectionLabel}>TRENDING NOW</Text> : null
          }
        />
      )}

      {/* No results */}
      {showNoResults && (
        <EmptyState
          icon="search-outline"
          title="No results in this city"
          body="Try a different search term or browse the feed"
        />
      )}

      {/* Results */}
      {!showTrending && !showNoResults && !error && results.length > 0 && (
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
  sectionLabel: {
    color: Colors.textMuted,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.5,
    paddingBottom: 10,
  },
  resultCount: { color: Colors.textMuted, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', paddingBottom: 8 },
});
