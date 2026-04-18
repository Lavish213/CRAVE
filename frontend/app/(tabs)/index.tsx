import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Animated,
  ActivityIndicator,
  FlatList,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useInfiniteQuery } from '@tanstack/react-query';
import { fetchPlaces, PlaceOut } from '../../src/api/places';
import { fetchCategories, CategoryOut } from '../../src/api/categories';
import { useCityStore } from '../../src/stores/cityStore';
import { useHitlistStore } from '../../src/stores/hitlistStore';
import { useToast } from '../../src/hooks/useToast';
import { useTrending } from '../../src/hooks/useTrending';
import { useLocation } from '../../src/hooks/useLocation';
import { Colors, Spacing, Radius } from '../../src/constants/colors';
import { getTier, TIERS, TierKey } from '../../src/utils/scoring';
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

const RADIUS_PRESETS = [
  { label: 'Walking', miles: 0.5 },
  { label: 'Biking', miles: 2 },
  { label: 'Close', miles: 5 },
  { label: 'Worth It', miles: 20 },
  { label: 'Road Trip', miles: 50 },
] as const;

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
  const initCities = useCityStore((s) => s.initCities);
  const { addSave, removeSave, isSaved } = useHitlistStore();
  const toast = useToast((s) => s.show);

  const userLocation = useLocation();
  const trending = useTrending();

  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [radiusMiles, setRadiusMiles] = useState(20);
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

  const places = data?.pages.flatMap(p => p.items) ?? [];
  const total = data?.pages[0]?.total ?? 0;
  const initialLoaded = data !== undefined;

  if (__DEV__ && data) {
    const lastPage = data.pages[data.pages.length - 1];
    console.log('[FEED] PLACES_LOADED', { page: lastPage?.page, count: places.length, total, sample: places[0] ? { id: places[0].id, category: places[0].category, categories: places[0].categories } : null });
  }

  useEffect(() => {
    fetchCategories().then((cats) => {
      if (__DEV__) console.log('[FEED] CATEGORIES_LOADED', { count: cats.length, names: cats.map((c) => c.name) });
      setAvailableCategories(cats.map((c) => c.name));
    });
  }, []);

  // Init cities when no city selected
  useEffect(() => {
    if (!selectedCity) initCities();
  }, [selectedCity?.id]);

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

  const rows = buildFeedRows(filteredPlaces);

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
      {userLocation && !selectedCity && (
        <View style={styles.radiusRow}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.radiusScrollContent}
          >
            {RADIUS_PRESETS.map((preset) => {
              const active = radiusMiles === preset.miles;
              return (
                <TouchableOpacity
                  key={preset.label}
                  style={[styles.radiusChip, active ? styles.radiusChipActive : styles.radiusChipInactive]}
                  onPress={() => {
                    setRadiusMiles(preset.miles);
                    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`${preset.label} radius`}
                >
                  <Text style={[styles.radiusChipText, active ? styles.radiusChipTextActive : styles.radiusChipTextInactive]}>
                    {preset.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>
      )}
      <TrendingStrip places={trending} onPress={(id) => router.push(`/place/${id}`)} />

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
  list: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.xxl, gap: Spacing.md },
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
  radiusRow: { paddingVertical: Spacing.xs },
  radiusScrollContent: { paddingHorizontal: Spacing.md, gap: 8 },
  radiusChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: Radius.pill, borderWidth: 1 },
  radiusChipActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  radiusChipInactive: { backgroundColor: 'transparent', borderColor: Colors.border },
  radiusChipText: { fontSize: 12, fontWeight: '600' },
  radiusChipTextActive: { color: Colors.text },
  radiusChipTextInactive: { color: Colors.textSecondary },
});
