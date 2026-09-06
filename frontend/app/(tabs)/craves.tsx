// app/(tabs)/craves.tsx
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { FlashList, ViewToken } from '@shopify/flash-list';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { SkeletonRowList } from '../../src/components/SkeletonCard';
import { useCravesStore } from '../../src/stores/cravesStore';
import { useToast } from '../../src/hooks/useToast';
import { Colors, Spacing, Radius } from '../../src/constants/colors';
import { withImageWidth, AVATAR_IMAGE_WIDTH } from '../../src/utils/imageUrl';
import { usePrefetchPlace } from '../../src/hooks/usePrefetchPlace';
import { PlaceCardCompact } from '../../src/components/PlaceCardCompact';
import { EmptyState } from '../../src/components/EmptyState';
import { ErrorState } from '../../src/components/ErrorState';
import { getCraveItems, CraveItem, getMyPlaceSaves, PlaceSaveItem } from '../../src/api/crave';
import { SavedPlace } from '../../src/api/saves';
import { useAuthStore } from '../../src/stores/authStore';
import { AuthSheet } from '../../src/components/AuthSheet';
import { ShareLinkSheet } from '../../src/components/ShareLinkSheet';
import { logRecommendationEvent, logRecommendationEvents } from '../../src/utils/recommendationEventQueue';

const VIEWABILITY_CONFIG = { itemVisiblePercentThreshold: 50, minimumViewTime: 250 };

type CravesRow =
  | { kind: 'save'; item: SavedPlace; position: number }
  | { kind: 'section'; section: 'craves' | 'added' }
  | { kind: 'crave'; item: CraveItem; matchedPosition: number | null }
  | { kind: 'place-save'; item: PlaceSaveItem; matchedPosition: number | null }
  | { kind: 'craves-loading' }
  | { kind: 'craves-error' }
  | { kind: 'place-saves-loading' }
  | { kind: 'place-saves-error' };

export default function CravesScreen() {
  const router = useRouter();
  const prefetchPlace = usePrefetchPlace();
  const { saves, loading: savesLoading, error: savesError, loadSaves, removeSave } = useCravesStore();
  const toast = useToast((s) => s.show);
  const user = useAuthStore((s) => s.user);

  const [craves, setCraves] = useState<CraveItem[]>([]);
  const [cravesLoading, setCravesLoading] = useState(false);
  const [cravesError, setCravesError] = useState(false);
  const [placeSaves, setPlaceSaves] = useState<PlaceSaveItem[]>([]);
  const [placeSavesLoading, setPlaceSavesLoading] = useState(false);
  const [placeSavesError, setPlaceSavesError] = useState(false);
  const [authVisible, setAuthVisible] = useState(false);
  const [shareVisible, setShareVisible] = useState(false);
  const [pullRefreshing, setPullRefreshing] = useState(false);

  const accountGenerationRef = useRef(0);
  const exposedRowsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    accountGenerationRef.current += 1;
    exposedRowsRef.current = new Set();
    setCraves([]);
    setCravesError(false);
    setPlaceSaves([]);
    setPlaceSavesError(false);
  }, [user?.id]);

  const loadCraves = React.useCallback(() => {
    const myGeneration = accountGenerationRef.current;
    setCravesLoading(true);
    setCravesError(false);
    return getCraveItems()
      .then((items) => {
        if (myGeneration !== accountGenerationRef.current) return;
        if (__DEV__) console.log('[CRAVES] CRAVES_LOADED', { count: items.length });
        setCraves(items);
      })
      .catch((err: unknown) => {
        if (myGeneration !== accountGenerationRef.current) return;
        if (__DEV__) {
          const status = typeof err === 'object' && err !== null && 'response' in err
            ? (err as { response?: { status?: number } }).response?.status
            : undefined;
          console.log('[CRAVES] CRAVES_ERROR', status, err instanceof Error ? err.message : String(err));
        }
        setCravesError(true);
      })
      .finally(() => {
        if (myGeneration !== accountGenerationRef.current) return;
        setCravesLoading(false);
      });
  }, []);

  const loadPlaceSaves = React.useCallback(() => {
    const myGeneration = accountGenerationRef.current;
    setPlaceSavesLoading(true);
    setPlaceSavesError(false);
    return getMyPlaceSaves()
      .then((items) => {
        if (myGeneration !== accountGenerationRef.current) return;
        setPlaceSaves(items);
      })
      .catch((err: unknown) => {
        if (myGeneration !== accountGenerationRef.current) return;
        if (__DEV__) console.log('[CRAVES] PLACE_SAVES_ERROR', err instanceof Error ? err.message : String(err));
        // Preserve any last successful data and mark failure explicitly.
        // A transport error is not a successful empty result.
        setPlaceSavesError(true);
      })
      .finally(() => {
        if (myGeneration !== accountGenerationRef.current) return;
        setPlaceSavesLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!user) return;
    void loadSaves(user.id);
  }, [user?.id, loadSaves]);

  useEffect(() => {
    if (!user) return;
    void loadCraves();
    void loadPlaceSaves();
  }, [user?.id, loadCraves, loadPlaceSaves]);

  const handlePullRefresh = React.useCallback(async () => {
    if (!user) return;
    setPullRefreshing(true);
    try {
      await Promise.all([loadSaves(user.id), loadCraves(), loadPlaceSaves()]);
    } finally {
      setPullRefreshing(false);
    }
  }, [user, loadSaves, loadCraves, loadPlaceSaves]);

  if (__DEV__) {
    console.log('[CRAVES] RENDER', {
      user: !!user,
      saves: saves.length,
      savesLoading,
      savesError,
      craves: craves.length,
      cravesLoading,
      cravesError,
      placeSaves: placeSaves.length,
      placeSavesLoading,
      placeSavesError,
    });
  }

  if (!user) {
    return (
      <>
        <EmptyState
          icon="person-circle-outline"
          title="Sign in to save places"
          body="Create a free account to build your Craves — places you save or share from TikTok, Instagram, and beyond."
          ctaLabel="Sign in"
          onCta={() => setAuthVisible(true)}
        />
        <AuthSheet visible={authVisible} onClose={() => setAuthVisible(false)} reason="craves" />
      </>
    );
  }

  if (savesLoading && saves.length === 0) {
    return (
      <View style={styles.list}>
        <SkeletonRowList count={4} />
      </View>
    );
  }

  if (savesError === 'auth_required' && saves.length === 0) {
    return (
      <>
        <EmptyState
          icon="person-circle-outline"
          title="Your session expired"
          body="Sign in again to see your saved places."
          ctaLabel="Sign in"
          onCta={() => setAuthVisible(true)}
        />
        <AuthSheet visible={authVisible} onClose={() => setAuthVisible(false)} reason="craves" />
      </>
    );
  }

  if (savesError && saves.length === 0) {
    return <ErrorState message={savesError} onRetry={() => void loadSaves(user.id)} />;
  }

  const shareBtn = (
    <TouchableOpacity
      style={styles.shareBtn}
      onPress={() => {
        void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        setShareVisible(true);
      }}
      accessibilityRole="button"
      accessibilityLabel="Share a link"
    >
      <Ionicons name="link-outline" size={16} color={Colors.primary} />
      <Text style={styles.shareBtnText}>Share a link</Text>
    </TouchableOpacity>
  );

  const handleShareSubmitted = () => {
    toast("Got it — we'll match this to a place shortly.");
    void loadCraves();
    void loadPlaceSaves();
  };

  const secondarySettled = !cravesLoading && !placeSavesLoading;
  const secondaryHealthy = !cravesError && !placeSavesError;
  if (
    saves.length === 0 &&
    craves.length === 0 &&
    placeSaves.length === 0 &&
    secondarySettled &&
    secondaryHealthy
  ) {
    return (
      <>
        <EmptyState
          icon="bookmark-outline"
          title="Start your food memory"
          body="Save places you want to visit, or share a TikTok/Instagram link and we'll find the place."
          ctaLabel="Share a link"
          onCta={() => setShareVisible(true)}
        />
        <ShareLinkSheet
          visible={shareVisible}
          onClose={() => setShareVisible(false)}
          onSubmitted={handleShareSubmitted}
        />
      </>
    );
  }

  const rows = useMemo<CravesRow[]>(() => {
    const next: CravesRow[] = saves.map((item, position) => ({ kind: 'save', item, position }));

    if (cravesLoading) {
      next.push({ kind: 'section', section: 'craves' }, { kind: 'craves-loading' });
    } else if (cravesError) {
      next.push({ kind: 'section', section: 'craves' }, { kind: 'craves-error' });
    } else if (craves.length > 0) {
      next.push({ kind: 'section', section: 'craves' });
      let matchedPosition = 0;
      for (const item of craves) {
        const position = item.matched_place_id ? matchedPosition++ : null;
        next.push({ kind: 'crave', item, matchedPosition: position });
      }
    }

    if (placeSavesLoading && placeSaves.length === 0) {
      next.push({ kind: 'section', section: 'added' }, { kind: 'place-saves-loading' });
    } else if (placeSavesError && placeSaves.length === 0) {
      next.push({ kind: 'section', section: 'added' }, { kind: 'place-saves-error' });
    } else if (placeSaves.length > 0) {
      next.push({ kind: 'section', section: 'added' });
      let matchedPosition = 0;
      for (const item of placeSaves) {
        const position = item.place_id ? matchedPosition++ : null;
        next.push({ kind: 'place-save', item, matchedPosition: position });
      }
      // Preserve stale-success truth if a refresh failed after data was
      // already visible: keep the rows and append a retryable status.
      if (placeSavesError) next.push({ kind: 'place-saves-error' });
    }

    return next;
  }, [saves, craves, cravesLoading, cravesError, placeSaves, placeSavesLoading, placeSavesError]);

  const handleViewableItemsChangedRef = useRef<(
    info: { viewableItems: ViewToken<CravesRow>[] }
  ) => void>(() => {});

  handleViewableItemsChangedRef.current = ({ viewableItems }) => {
    const events: Parameters<typeof logRecommendationEvents>[0] = [];

    for (const token of viewableItems) {
      if (!token.isViewable || !token.item) continue;
      const row = token.item;

      if (row.kind === 'save') {
        const key = `save:${row.item.id}`;
        if (exposedRowsRef.current.has(key)) continue;
        exposedRowsRef.current.add(key);
        events.push({
          surface: 'craves',
          event_type: 'impression',
          place_id: row.item.id,
          position: row.position,
          rank_percentile: row.item.rank_percentile,
          city_id: row.item.city_id ?? null,
        });
        continue;
      }

      if (row.kind === 'crave' && row.item.matched_place_id && row.matchedPosition !== null) {
        const key = `crave:${row.item.id}`;
        if (exposedRowsRef.current.has(key)) continue;
        exposedRowsRef.current.add(key);
        events.push({
          surface: 'craves',
          event_type: 'impression',
          place_id: row.item.matched_place_id,
          position: row.matchedPosition,
        });
        continue;
      }

      if (row.kind === 'place-save' && row.item.place_id && row.matchedPosition !== null) {
        const key = `place-save:${row.item.id}`;
        if (exposedRowsRef.current.has(key)) continue;
        exposedRowsRef.current.add(key);
        events.push({
          surface: 'craves',
          event_type: 'impression',
          place_id: row.item.place_id,
          position: row.matchedPosition,
        });
      }
    }

    if (events.length > 0) logRecommendationEvents(events);
  };

  const onViewableItemsChanged = useRef((info: { viewableItems: ViewToken<CravesRow>[] }) => {
    handleViewableItemsChangedRef.current(info);
  }).current;

  return (
    <View style={styles.container}>
      <FlashList
        data={rows}
        keyExtractor={(row, index) => {
          switch (row.kind) {
            case 'save': return `save-${row.item.id}`;
            case 'crave': return `crave-${row.item.id}`;
            case 'place-save': return `place-save-${row.item.id}`;
            case 'section': return `section-${row.section}`;
            default: return `${row.kind}-${index}`;
          }
        }}
        getItemType={(row) => row.kind}
        viewabilityConfig={VIEWABILITY_CONFIG}
        onViewableItemsChanged={onViewableItemsChanged}
        refreshControl={
          <RefreshControl
            refreshing={pullRefreshing}
            onRefresh={handlePullRefresh}
            tintColor={Colors.primary}
          />
        }
        renderItem={({ item: row }) => {
          if (row.kind === 'save') {
            return (
              <View style={styles.rowSpacer}>
                <PlaceCardCompact
                  place={row.item}
                  visited={row.item.visited}
                  hasNotes={!!row.item.notes}
                  onPress={() => {
                    logRecommendationEvent({
                      surface: 'craves',
                      event_type: 'click',
                      place_id: row.item.id,
                      position: row.position,
                      rank_percentile: row.item.rank_percentile,
                      city_id: row.item.city_id ?? null,
                    });
                    router.push(`/place/${row.item.id}`);
                  }}
                  onPressIn={() => prefetchPlace(row.item.id)}
                  rightAction={
                    <TouchableOpacity
                      onPress={async () => {
                        void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                        const err = await removeSave(row.item.id, user.id, {
                          surface: 'craves',
                          rank_percentile: row.item.rank_percentile,
                          city_id: row.item.city_id ?? null,
                        });
                        toast(err ?? 'Removed from Saves');
                      }}
                      style={styles.removeBtn}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                      accessibilityLabel={`Remove ${row.item.name} from saves`}
                      accessibilityRole="button"
                    >
                      <Ionicons name="close" size={18} color={Colors.textSecondary} />
                    </TouchableOpacity>
                  }
                />
              </View>
            );
          }

          if (row.kind === 'section') {
            return (
              <View style={styles.cravesHeader}>
                <Text style={styles.cravesTitle}>{row.section === 'craves' ? 'Craves' : 'Added'}</Text>
                <Text style={styles.cravesSub}>
                  {row.section === 'craves'
                    ? "Places you've craved, tracked by CRAVE"
                    : 'Places you typed in by name'}
                </Text>
              </View>
            );
          }

          if (row.kind === 'craves-loading' || row.kind === 'place-saves-loading') {
            return <ActivityIndicator color={Colors.primary} style={styles.sectionSpinner} />;
          }

          if (row.kind === 'craves-error' || row.kind === 'place-saves-error') {
            const isCravesError = row.kind === 'craves-error';
            return (
              <TouchableOpacity
                style={styles.inlineError}
                onPress={() => void (isCravesError ? loadCraves() : loadPlaceSaves())}
                accessibilityRole="button"
                accessibilityLabel={isCravesError ? 'Retry loading Craves' : 'Retry loading added places'}
              >
                <Text style={styles.cravesSub}>
                  {isCravesError
                    ? "Couldn't load Craves right now — tap to retry."
                    : "Couldn't load added places right now — tap to retry."}
                </Text>
              </TouchableOpacity>
            );
          }

          if (row.kind === 'crave') {
            return (
              <View style={styles.craveRow}>
                {row.item.thumbnail_url ? (
                  <Image
                    source={withImageWidth(row.item.thumbnail_url, AVATAR_IMAGE_WIDTH)}
                    style={styles.craveThumb}
                    contentFit="cover"
                    cachePolicy="memory-disk"
                  />
                ) : null}
                <View style={styles.craveMeta}>
                  <Text style={styles.craveName} numberOfLines={1}>
                    {row.item.parsed_place_name ?? row.item.url}
                  </Text>
                  <Text style={row.item.matched_place_id ? styles.craveStatusMatched : styles.craveStatusPending}>
                    {row.item.matched_place_id ? '● Matched' : 'Searching…'}
                    {row.item.author_name ? `  ·  @${row.item.author_name}` : ''}
                  </Text>
                </View>
                {row.item.matched_place_id ? (
                  <TouchableOpacity
                    style={styles.craveOpenBtn}
                    onPress={() => {
                      logRecommendationEvent({
                        surface: 'craves',
                        event_type: 'click',
                        place_id: row.item.matched_place_id!,
                        position: row.matchedPosition,
                      });
                      router.push(`/place/${row.item.matched_place_id!}`);
                    }}
                    accessibilityRole="button"
                    accessibilityLabel={`Open matched place for ${row.item.parsed_place_name ?? 'this place'}`}
                  >
                    <Text style={styles.craveViewBtn}>View →</Text>
                  </TouchableOpacity>
                ) : null}
              </View>
            );
          }

          return (
            <View style={styles.craveRow}>
              <View style={styles.craveMeta}>
                <Text style={styles.craveName} numberOfLines={1}>{row.item.place_name}</Text>
                <Text style={row.item.place_id ? styles.craveStatusMatched : styles.craveStatusPending}>
                  {row.item.place_id ? '● Matched' : 'Searching…'}
                </Text>
              </View>
              {row.item.place_id ? (
                <TouchableOpacity
                  style={styles.craveOpenBtn}
                  onPress={() => {
                    logRecommendationEvent({
                      surface: 'craves',
                      event_type: 'click',
                      place_id: row.item.place_id!,
                      position: row.matchedPosition,
                    });
                    router.push(`/place/${row.item.place_id!}`);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`Open matched place for ${row.item.place_name}`}
                >
                  <Text style={styles.craveViewBtn}>View →</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          );
        }}
        contentContainerStyle={styles.list}
        ListHeaderComponent={
          <View style={styles.screenHeader}>
            <View style={styles.screenHeaderLeft}>
              <Text style={styles.screenTitle}>Saves</Text>
              {saves.length > 0 ? (
                <View style={styles.countBadge}>
                  <Text style={styles.countBadgeText}>{saves.length}</Text>
                </View>
              ) : null}
            </View>
            {shareBtn}
          </View>
        }
      />
      <ShareLinkSheet
        visible={shareVisible}
        onClose={() => setShareVisible(false)}
        onSubmitted={handleShareSubmitted}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  list: { padding: Spacing.md, paddingBottom: Spacing.xxl },
  rowSpacer: { marginBottom: Spacing.sm },
  screenHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: Spacing.md,
  },
  screenHeaderLeft: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  shareBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    minHeight: 44,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  shareBtnText: { fontSize: 13, fontWeight: '700', color: Colors.primary },
  screenTitle: { fontSize: 22, fontWeight: '800', color: Colors.text },
  countBadge: {
    backgroundColor: Colors.primary,
    borderRadius: Radius.full,
    minWidth: 22,
    height: 22,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.xs,
  },
  countBadgeText: { color: Colors.text, fontSize: 11, fontWeight: '800' },
  removeBtn: {
    padding: Spacing.sm,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cravesHeader: { paddingTop: Spacing.lg, paddingBottom: Spacing.sm },
  cravesTitle: { fontSize: 20, fontWeight: '800', color: Colors.text },
  cravesSub: { fontSize: 12, color: Colors.textSecondary, marginTop: Spacing.xs },
  sectionSpinner: { marginVertical: Spacing.lg },
  inlineError: {
    minHeight: 44,
    justifyContent: 'center',
    paddingVertical: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  craveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    padding: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.sm,
  },
  craveThumb: {
    width: 40,
    height: 40,
    borderRadius: Radius.sm,
    backgroundColor: Colors.surfaceElevated,
  },
  craveMeta: { flex: 1 },
  craveName: { color: Colors.text, fontSize: 14, fontWeight: '600' },
  craveStatusMatched: { fontSize: 12, marginTop: 2, color: Colors.success },
  craveStatusPending: { fontSize: 12, marginTop: 2, color: Colors.textSecondary },
  craveOpenBtn: {
    padding: 8,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  craveViewBtn: { color: Colors.primary, fontSize: 13, fontWeight: '700' },
});
