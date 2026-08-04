// app/(tabs)/craves.tsx
//
// Renamed from hitlist.tsx — "Hitlist" was never this app's actual name for
// this feature; the tab bar label was "Saves" and "Hitlist" was informal
// drift. This screen (and the whole tab) is called Craves: bookmarked
// places plus shared TikTok/Instagram/YouTube links working toward a match.
import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Image,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { SkeletonRowList } from '../../src/components/SkeletonCard';
import { useCravesStore } from '../../src/stores/cravesStore';
import { useToast } from '../../src/hooks/useToast';
import { Colors, Spacing, Radius } from '../../src/constants/colors';
import { PlaceCardCompact } from '../../src/components/PlaceCardCompact';
import { EmptyState } from '../../src/components/EmptyState';
import { ErrorState } from '../../src/components/ErrorState';
import { getCraveItems, CraveItem, getMyPlaceSaves, PlaceSaveItem } from '../../src/api/crave';
import { useAuthStore } from '../../src/stores/authStore';
import { AuthSheet } from '../../src/components/AuthSheet';
import { ShareLinkSheet } from '../../src/components/ShareLinkSheet';

export default function CravesScreen() {
  const router = useRouter();
  const { saves, loading: savesLoading, error: savesError, loadSaves, removeSave } = useCravesStore();
  const toast = useToast((s) => s.show);
  const user = useAuthStore((s) => s.user);

  const [craves, setCraves] = useState<CraveItem[]>([]);
  const [cravesLoading, setCravesLoading] = useState(false);
  const [cravesError, setCravesError] = useState(false);
  const [placeSaves, setPlaceSaves] = useState<PlaceSaveItem[]>([]);
  const [authVisible, setAuthVisible] = useState(false);
  const [shareVisible, setShareVisible] = useState(false);

  const loadCraves = React.useCallback(() => {
    setCravesLoading(true);
    setCravesError(false);
    return getCraveItems()
      .then((items) => {
        if (__DEV__) console.log('[CRAVES] CRAVES_LOADED', { count: items.length });
        setCraves(items);
      })
      .catch((err) => {
        if (__DEV__) console.log('[CRAVES] CRAVES_ERROR', err?.response?.status, err?.message);
        setCravesError(true);
      })
      .finally(() => setCravesLoading(false));
  }, []);

  // "Just the name" adds — separate list from CraveItems (which come from
  // shared links), fetched and shown alongside so a manual add doesn't
  // vanish into a black hole after submitting.
  const loadPlaceSaves = React.useCallback(() => {
    return getMyPlaceSaves()
      .then((items) => setPlaceSaves(items))
      .catch(() => setPlaceSaves([]));
  }, []);

  // Load backend saves whenever user changes
  useEffect(() => {
    if (!user) return;
    loadSaves(user.id);
  }, [user?.id]);

  // Load craves + manual place-saves whenever user changes
  useEffect(() => {
    if (!user) return;
    loadCraves();
    loadPlaceSaves();
  }, [user?.id, loadCraves, loadPlaceSaves]);

  const [pullRefreshing, setPullRefreshing] = useState(false);
  const handlePullRefresh = React.useCallback(async () => {
    if (!user) return;
    setPullRefreshing(true);
    try {
      await Promise.all([loadSaves(user.id), loadCraves(), loadPlaceSaves()]);
    } finally {
      setPullRefreshing(false);
    }
  }, [user, loadSaves, loadCraves, loadPlaceSaves]);

  if (__DEV__) console.log('[CRAVES] RENDER', { user: !!user, saves: saves.length, savesLoading, savesError, craves: craves.length });

  // Not signed in
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

  // Loading initial saves
  if (savesLoading && saves.length === 0) {
    return (
      <View style={styles.list}>
        <SkeletonRowList count={4} />
      </View>
    );
  }

  // Session expired/invalid — retrying the same request would just fail
  // the same way again. Previously this fell through to the generic
  // ErrorState below, showing an infinite "retry" loop with no way out.
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

  // Error loading saves (and no cached data)
  if (savesError && saves.length === 0) {
    return (
      <ErrorState
        message={savesError}
        onRetry={() => loadSaves(user.id)}
      />
    );
  }

  const shareBtn = (
    <TouchableOpacity
      style={styles.shareBtn}
      onPress={() => {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
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
    loadCraves();
    loadPlaceSaves();
  };

  // True empty
  if (saves.length === 0 && craves.length === 0 && placeSaves.length === 0 && !cravesLoading) {
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

  return (
    <View style={styles.container}>
      <FlatList
        data={saves}
        keyExtractor={(p) => p.id}
        refreshControl={
          <RefreshControl
            refreshing={pullRefreshing}
            onRefresh={handlePullRefresh}
            tintColor={Colors.primary}
          />
        }
        renderItem={({ item }) => (
          <PlaceCardCompact
            place={item}
            onPress={() => router.push(`/place/${item.id}`)}
            rightAction={
              <TouchableOpacity
                onPress={async () => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                  const err = await removeSave(item.id, user.id);
                  if (err) {
                    toast(err);
                  } else {
                    toast('Removed from Saves');
                  }
                }}
                style={styles.removeBtn}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                accessibilityLabel={`Remove ${item.name} from saves`}
                accessibilityRole="button"
              >
                <Ionicons name="close" size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            }
          />
        )}
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
        ListFooterComponent={
          <>
            {cravesLoading ? (
              <View style={styles.cravesSection}>
                <ActivityIndicator color={Colors.primary} style={{ marginVertical: 16 }} />
              </View>
            ) : cravesError ? (
              <View style={styles.cravesSection}>
                <Text style={styles.cravesSub}>Couldn't load Craves right now.</Text>
              </View>
            ) : craves.length > 0 ? (
              <View style={styles.cravesSection}>
                <View style={styles.cravesHeader}>
                  <Text style={styles.cravesTitle}>Craves</Text>
                  <Text style={styles.cravesSub}>Places you've craved, tracked by CRAVE</Text>
                </View>
                {craves.map((item) => (
                  <View key={item.id} style={styles.craveRow}>
                    {item.thumbnail_url ? (
                      <Image source={{ uri: item.thumbnail_url }} style={styles.craveThumb} />
                    ) : null}
                    <View style={styles.craveMeta}>
                      <Text style={styles.craveName} numberOfLines={1}>
                        {item.parsed_place_name ?? item.url}
                      </Text>
                      <Text style={item.matched_place_id ? styles.craveStatusMatched : styles.craveStatusPending}>
                        {item.matched_place_id ? '● Matched' : 'Searching…'}
                        {item.author_name ? `  ·  @${item.author_name}` : ''}
                      </Text>
                    </View>
                    {item.matched_place_id && (
                      <TouchableOpacity
                        style={styles.craveOpenBtn}
                        onPress={() => router.push(`/place/${item.matched_place_id!}`)}
                        accessibilityRole="button"
                        accessibilityLabel={`Open matched place for ${item.parsed_place_name ?? 'this place'}`}
                      >
                        <Text style={styles.craveViewBtn}>View →</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                ))}
              </View>
            ) : null}

            {placeSaves.length > 0 ? (
              <View style={styles.cravesSection}>
                <View style={styles.cravesHeader}>
                  <Text style={styles.cravesTitle}>Added</Text>
                  <Text style={styles.cravesSub}>Places you typed in by name</Text>
                </View>
                {placeSaves.map((item) => (
                  <View key={item.id} style={styles.craveRow}>
                    <View style={styles.craveMeta}>
                      <Text style={styles.craveName} numberOfLines={1}>
                        {item.place_name}
                      </Text>
                      <Text style={item.place_id ? styles.craveStatusMatched : styles.craveStatusPending}>
                        {item.place_id ? '● Matched' : 'Searching…'}
                      </Text>
                    </View>
                    {item.place_id && (
                      <TouchableOpacity
                        style={styles.craveOpenBtn}
                        onPress={() => router.push(`/place/${item.place_id!}`)}
                        accessibilityRole="button"
                        accessibilityLabel={`Open matched place for ${item.place_name}`}
                      >
                        <Text style={styles.craveViewBtn}>View →</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                ))}
              </View>
            ) : null}
          </>
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
  list: { padding: Spacing.md, gap: Spacing.sm, paddingBottom: Spacing.xxl },
  screenHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: Spacing.md,
  },
  screenHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  shareBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  shareBtnText: { fontSize: 13, fontWeight: '700', color: Colors.primary },
  screenTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: Colors.text,
  },
  countBadge: {
    backgroundColor: Colors.primary,
    borderRadius: Radius.full,
    minWidth: 22,
    height: 22,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.xs,
  },
  countBadgeText: {
    color: Colors.text,
    fontSize: 11,
    fontWeight: '800',
  },
  removeBtn: {
    padding: Spacing.sm,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cravesSection: { paddingTop: Spacing.lg, paddingBottom: Spacing.sm },
  cravesHeader: {
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  cravesTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: Colors.text,
  },
  cravesSub: {
    fontSize: 12,
    color: Colors.textMuted,
    marginTop: Spacing.xs,
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
  craveStatusPending: { fontSize: 12, marginTop: 2, color: Colors.textMuted },
  craveOpenBtn: {
    padding: 8,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  craveViewBtn: {
    color: Colors.primary,
    fontSize: 13,
    fontWeight: '700',
  },
});
