// app/(tabs)/index.tsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { fetchPlaces, PlaceOut } from '../../src/api/places';
import { useCityStore } from '../../src/stores/cityStore';
import { useHitlistStore } from '../../src/stores/hitlistStore';
import { useToast } from '../../src/hooks/useToast';
import { useTrending } from '../../src/hooks/useTrending';
import { Colors, Spacing } from '../../src/constants/colors';
import { getTier, TIERS, TierKey } from '../../src/utils/scoring';
import { PlaceCard } from '../../src/components/PlaceCard';
import { SectionHeader } from '../../src/components/SectionHeader';
import { CitySelectorStrip } from '../../src/components/CitySelectorStrip';
import { TrendingStrip } from '../../src/components/TrendingStrip';
import { ErrorState } from '../../src/components/ErrorState';
import { EmptyState } from '../../src/components/EmptyState';
import { SkeletonFeed } from '../../src/components/SkeletonCard';
import { FilterSheet, FilterState, EMPTY_FILTERS, hasActiveFilters } from '../../src/components/FilterSheet';

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
    buckets[getTier(p.rank_score).key].push(p);
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
  const selectedCity = useCityStore((s) => s.selectedCity);
  const { addSave, removeSave, isSaved } = useHitlistStore();
  const toast = useToast((s) => s.show);

  const trending = useTrending();

  const [places, setPlaces] = useState<PlaceOut[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);
  const [error, setError] = useState(false);
  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);

  const loadingRef = useRef(false);
  const cancelledRef = useRef(false);

  const loadPage = useCallback(async (p: number, reset = false) => {
    if (loadingRef.current) return;
    if (!selectedCity) return;

    loadingRef.current = true;
    cancelledRef.current = false;
    if (!reset) setLoading(true);
    setError(false);

    try {
      const res = await fetchPlaces({ city_id: selectedCity.id, page: p, page_size: 40 });
      if (cancelledRef.current) return;
      setTotal(res.total);
      setPlaces((prev) => reset ? res.items : [...prev, ...res.items]);
      setPage(p);
    } catch {
      if (!cancelledRef.current) setError(true);
    } finally {
      if (!cancelledRef.current) {
        loadingRef.current = false;
        setLoading(false);
        setRefreshing(false);
        setInitialLoaded(true);
      }
    }
  }, [selectedCity]);

  useEffect(() => {
    cancelledRef.current = true;
    loadingRef.current = false;
    setPlaces([]);
    setPage(1);
    setInitialLoaded(false);
    setError(false);
    loadPage(1, true);
  }, [selectedCity?.id]);

  const handleRefresh = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setRefreshing(true);
    loadPage(1, true);
  };
  const handleEndReached = () => {
    if (!loadingRef.current && places.length < total) loadPage(page + 1);
  };

  const availableCategories = useMemo(() => {
    const cats = new Set(places.map(p => p.category).filter(Boolean) as string[]);
    return Array.from(cats).sort();
  }, [places]);

  const filteredPlaces = useMemo(() => {
    if (!hasActiveFilters(filters)) return places;
    return places.filter(p => {
      if (filters.priceTiers.length > 0 && (p.price_tier == null || !filters.priceTiers.includes(p.price_tier))) return false;
      if (filters.categories.length > 0 && (p.category == null || !filters.categories.includes(p.category))) return false;
      return true;
    });
  }, [places, filters]);

  const rows = buildFeedRows(filteredPlaces);

  return (
    <View style={styles.container}>
      {/* App header */}
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
      <TrendingStrip places={trending} onPress={(id) => router.push(`/place/${id}`)} />

      {!initialLoaded ? (
        <View style={styles.skeletonWrap}><SkeletonFeed count={4} /></View>
      ) : error ? (
        <ErrorState message="Couldn't load places" onRetry={() => loadPage(1, true)} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon="search-outline"
          title="Nothing here yet"
          body="Try selecting a different city"
        />
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(row, i) => row.kind === 'place' ? row.place.id : `header-${i}`}
          renderItem={({ item: row }) => {
            if (row.kind === 'header') {
              const tier = TIERS[row.tierKey];
              return (
                <SectionHeader
                  label={tier.sectionLabel}
                  subtext={tier.sectionSubtext}
                  count={row.count}
                />
              );
            }
            return (
              <PlaceCard
                place={row.place}
                onPress={() => router.push(`/place/${row.place.id}`)}
                onSave={() => {
                  if (isSaved(row.place.id)) {
                    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
                    removeSave(row.place.id);
                    toast('Removed from Hitlist');
                  } else {
                    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
                    addSave(row.place);
                    toast('Saved to Hitlist');
                  }
                }}
                saved={isSaved(row.place.id)}
              />
            );
          }}
          contentContainerStyle={styles.list}
          onEndReached={handleEndReached}
          onEndReachedThreshold={0.3}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor={Colors.primary}
            />
          }
          ListFooterComponent={
            loading ? <ActivityIndicator color={Colors.primary} style={styles.listFooter} /> : null
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
  list: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.xxl, gap: Spacing.sm },
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
