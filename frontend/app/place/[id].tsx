// app/place/[id].tsx
import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Linking,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useLocalSearchParams, useNavigation, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { useQuery } from '@tanstack/react-query';
import { fetchPlaceDetail, PlaceOut } from '../../src/api/places';
import { getPlaceMenu, MenuItem } from '../../src/api/menu';
import { CraveItem, getCravesForPlace } from '../../src/api/crave';
import { useCravesStore } from '../../src/stores/cravesStore';
import { useAuthStore } from '../../src/stores/authStore';
import { useToast } from '../../src/hooks/useToast';
import { useImagePicker } from '../../src/hooks/useImagePicker';
import { useUploadImage } from '../../src/hooks/useUploadImage';
import { useImageStatusPoll } from '../../src/hooks/useImageStatusPoll';
import { Colors, Spacing, Radius } from '../../src/constants/colors';
import { getTier, getBadges, formatPrice } from '../../src/utils/scoring';
import { fetchMyRankings } from '../../src/api/social';
import { formatScore, tierColor } from '../../src/utils/rankScore';
import { relativeTime } from '../../src/utils/time';
import { ImageGallery } from '../../src/components/ImageGallery';
import { ReportPhotoSheet } from '../../src/components/ReportPhotoSheet';
import { TierBadge } from '../../src/components/TierBadge';
import { ErrorState } from '../../src/components/ErrorState';

const HEADER_RIGHT_BTN = {
  marginRight: 4,
  padding: 8,
  minWidth: 44,
  minHeight: 44,
  alignItems: 'center' as const,
  justifyContent: 'center' as const,
};

function DetailSkeleton() {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: Colors.background }} scrollEnabled={false}>
      {/* Hero image skeleton */}
      <View style={{ width: '100%', height: 280, backgroundColor: Colors.surface }} />
      {/* Identity block */}
      <View style={{ padding: Spacing.lg, gap: Spacing.sm }}>
        <View style={{ width: 80, height: 22, borderRadius: Radius.sm, backgroundColor: Colors.surface }} />
        <View style={{ width: '75%', height: 28, borderRadius: Radius.sm, backgroundColor: Colors.surface }} />
        <View style={{ width: '50%', height: 16, borderRadius: Radius.sm, backgroundColor: Colors.surface }} />
        <View style={{ width: '60%', height: 14, borderRadius: Radius.sm, backgroundColor: Colors.surface }} />
      </View>
      {/* Trust badge row skeleton */}
      <View style={{ flexDirection: 'row', gap: Spacing.sm, paddingHorizontal: Spacing.lg, paddingBottom: Spacing.md }}>
        {[80, 100, 70].map((w, i) => (
          <View key={i} style={{ width: w, height: 28, borderRadius: Radius.pill, backgroundColor: Colors.surface }} />
        ))}
      </View>
      {/* Action row skeleton */}
      <View style={{ flexDirection: 'row', gap: Spacing.sm, padding: Spacing.lg }}>
        {[72, 88, 80].map((w, i) => (
          <View key={i} style={{ width: w, height: 40, borderRadius: Radius.pill, backgroundColor: Colors.surface }} />
        ))}
      </View>
    </ScrollView>
  );
}

export default function PlaceDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const navigation = useNavigation();
  const router = useRouter();
  const { addSave, removeSave, isSaved } = useCravesStore();
  const user = useAuthStore((s) => s.user);
  const toast = useToast((s) => s.show);
  const { pick } = useImagePicker();
  const { upload } = useUploadImage();

  const { data: place, isLoading, isError, refetch } = useQuery({
    queryKey: ['place', id],
    queryFn: () => fetchPlaceDetail(id!),
    staleTime: 5 * 60 * 1000,  // 5 min
    enabled: !!id,
  });

  // The whole ranked list rather than a per-place lookup: react-query
  // caches one copy across every place screen, so this costs a single
  // request per session instead of one per place opened.
  const { data: myRankings } = useQuery({
    queryKey: ['myRankings'],
    queryFn: fetchMyRankings,
    staleTime: 60 * 1000,
    enabled: !!user,
  });
  const myRanking = myRankings?.find((r) => r.place_id === id);

  const [reportImageId, setReportImageId] = useState<string | null>(null);

  const [isAddingPhoto, setIsAddingPhoto] = useState(false);
  const [pendingImageId, setPendingImageId] = useState<string | undefined>();
  const { status: uploadStatus, error: uploadError } = useImageStatusPoll(pendingImageId);

  useEffect(() => {
    if (!pendingImageId || !uploadStatus) return;
    if (uploadStatus === 'ready') {
      toast('Photo added');
      setPendingImageId(undefined);
      refetch();
    } else if (uploadStatus === 'failed') {
      toast(uploadError ?? 'Photo failed to process');
      setPendingImageId(undefined);
    }
  }, [uploadStatus, uploadError, pendingImageId, toast, refetch]);

  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [menuVerifiedAt, setMenuVerifiedAt] = useState<string | null>(null);
  const [menuLoading, setMenuLoading] = useState(true);
  const [menuExpanded, setMenuExpanded] = useState(false);

  // Fetch menu separately (not worth a useQuery for this small side-load)
  useEffect(() => {
    if (!id) return;
    setMenuLoading(true);
    getPlaceMenu(id)
      .then((m) => {
        setMenuItems(m.items);
        setMenuVerifiedAt(m.lastVerifiedAt);
      })
      .catch(() => {
        setMenuItems([]);
        setMenuVerifiedAt(null);
      })
      .finally(() => setMenuLoading(false));
  }, [id]);

  const [craves, setCraves] = useState<CraveItem[]>([]);

  // Matched shares for this place — "seen on TikTok/YouTube" social proof.
  // Public endpoint, no auth needed, silently empty on failure (this is
  // supplementary content, not worth an error state of its own).
  useEffect(() => {
    if (!id) return;
    getCravesForPlace(id)
      .then((items) => setCraves(items))
      .catch(() => setCraves([]));
  }, [id]);

  const handleShare = useCallback(() => {
    if (!place) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    Share.share({
      message: `${place.name} — ${place.category ?? 'Restaurant'} in ${place.address ? place.address.split(',').pop()?.trim() ?? 'your city' : 'your city'}. Found on CRAVE.`,
    });
  }, [place]);

  useEffect(() => {
    if (place) {
      navigation.setOptions({
        title: place.name,
        headerRight: () => (
          <TouchableOpacity
            onPress={handleShare}
            style={HEADER_RIGHT_BTN}
            accessibilityLabel="Share this place"
            accessibilityRole="button"
          >
            <Ionicons name="share-outline" size={22} color={Colors.text} />
          </TouchableOpacity>
        ),
      });
    }
  }, [place, handleShare]);

  if (isLoading) return <DetailSkeleton />;

  if (isError || !place) {
    return <ErrorState message="Couldn't load this place" onRetry={() => refetch()} />;
  }

  const tier = getTier(place.rank_score);
  const badges = getBadges(place);
  const price = place.price ?? formatPrice(place);
  const saved = isSaved(place.id);
  const allImages: string[] = place.images?.length ? place.images : (place.image ? [place.image] : []);
  const previewMenu = menuExpanded ? menuItems : menuItems.slice(0, 5);

  // Group menu items by category
  const menuByCategory: Record<string, MenuItem[]> = {};
  for (const item of previewMenu) {
    const cat = item.category ?? 'Menu';
    if (!menuByCategory[cat]) menuByCategory[cat] = [];
    menuByCategory[cat].push(item);
  }

  const handleSave = async () => {
    if (!user) return;
    if (saved) {
      const err = await removeSave(place.id, user.id);
      if (err) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
        toast(err);
      } else {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
        toast('Removed from Saves');
      }
    } else {
      const err = await addSave(place, user.id);
      if (err) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
        toast(err);
      } else {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        toast('Saved');
      }
    }
  };

  const handleAddPhoto = async (photoType: 'food' | 'menu' = 'food') => {
    if (!user) {
      toast('Sign in to add photos');
      return;
    }
    try {
      const image = await pick();
      if (!image) return; // user canceled

      setIsAddingPhoto(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      const imageId = await upload(image, place.id, photoType);
      setPendingImageId(imageId);
      toast(photoType === 'menu' ? 'Uploading menu photo…' : 'Uploading photo…');
    } catch (err) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      toast(err instanceof Error ? err.message : 'Could not upload photo');
    } finally {
      setIsAddingPhoto(false);
    }
  };

  const handleDirections = () => {
    if (!place.lat || !place.lng) return;
    const mapsUrl = `maps://?q=${encodeURIComponent(place.name)}&ll=${place.lat},${place.lng}`;
    Linking.canOpenURL(mapsUrl).then((ok) => {
      Linking.openURL(ok ? mapsUrl : `https://maps.google.com/?q=${place.lat},${place.lng}`);
    });
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Hero gallery */}
      <ImageGallery
        images={allImages}
        gpsVerified={place.images?.length ? place.image_gps_verified : undefined}
      />

      {/* Identity */}
      <View style={styles.identity}>
        <View style={styles.identityTop}>
          <TierBadge tier={tier} />
          {price ? (
            <Text style={styles.price}>{price}</Text>
          ) : null}
        </View>
        <Text style={styles.name}>{place.name}</Text>
        <Text style={styles.meta}>
          {[place.category, place.address].filter(Boolean).join('  ·  ')}
        </Text>
      </View>

      {/* Emoji badge chips */}
      {badges.length > 0 && (
        <View style={styles.badgeChips}>
          {badges.map((b) => (
            <View key={b.label} style={styles.chip}>
              <Text style={styles.chipText}>{b.emoji} {b.label}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Primary CTA — deliberately one prominent action, visually distinct
          from the secondary row below it, rather than a fifth equal-weight
          icon button nobody would find. Ranking is the thing this app wants
          you to do; saving and sharing are supporting acts. */}
      <TouchableOpacity
        style={[styles.rankCta, myRanking ? styles.rankCtaRanked : null]}
        onPress={() => {
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
          if (!user) {
            toast('Sign in to rank places');
            return;
          }
          router.push(`/rank/${place.id}`);
        }}
        activeOpacity={0.85}
        accessibilityRole="button"
        accessibilityLabel={
          myRanking
            ? `You ranked this ${formatScore(myRanking.rank_score)} out of 10`
            : 'I ate here — rank this place'
        }
      >
        {myRanking ? (
          <>
            <View style={[styles.rankScoreDot, { borderColor: tierColor(myRanking.tier) }]}>
              <Text style={[styles.rankScoreDotText, { color: tierColor(myRanking.tier) }]}>
                {formatScore(myRanking.rank_score)}
              </Text>
            </View>
            <Text style={styles.rankCtaRankedText}>Your score · tap to re-rank</Text>
          </>
        ) : (
          <>
            <Ionicons name="restaurant" size={18} color="#FFFFFF" />
            <Text style={styles.rankCtaText}>I ate here</Text>
          </>
        )}
      </TouchableOpacity>

      {/* Action row */}
      <View style={styles.actions}>
        <TouchableOpacity
          style={[styles.actionBtn, saved && styles.actionBtnSaved]}
          onPress={handleSave}
          accessibilityLabel={saved ? 'Remove from Saves' : 'Save to Saves'}
          accessibilityRole="button"
        >
          <Ionicons
            name={saved ? 'bookmark' : 'bookmark-outline'}
            size={18}
            color={saved ? Colors.primary : Colors.text}
          />
          <Text style={[styles.actionLabel, saved && styles.actionLabelSaved]}>
            {saved ? 'Saved' : 'Save'}
          </Text>
        </TouchableOpacity>

        {place.website ? (
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
              Linking.openURL(place.website!);
            }}
            accessibilityLabel="Open website"
            accessibilityRole="link"
          >
            <Ionicons name="globe-outline" size={18} color={Colors.text} />
            <Text style={styles.actionLabel}>Website</Text>
          </TouchableOpacity>
        ) : null}

        {place.grubhub_url ? (
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
              Linking.openURL(place.grubhub_url!);
            }}
            accessibilityLabel="Order online"
            accessibilityRole="link"
          >
            <Ionicons name="restaurant-outline" size={18} color={Colors.text} />
            <Text style={styles.actionLabel}>Order</Text>
          </TouchableOpacity>
        ) : null}

        {place.lat && place.lng ? (
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
              handleDirections();
            }}
            accessibilityLabel="Get directions"
            accessibilityRole="button"
          >
            <Ionicons name="navigate-outline" size={18} color={Colors.text} />
            <Text style={styles.actionLabel}>Directions</Text>
          </TouchableOpacity>
        ) : null}

        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => handleAddPhoto('food')}
          disabled={isAddingPhoto || !!pendingImageId}
          accessibilityLabel="Add a photo"
          accessibilityRole="button"
        >
          {isAddingPhoto || pendingImageId ? (
            <ActivityIndicator size="small" color={Colors.text} />
          ) : (
            <Ionicons name="camera-outline" size={18} color={Colors.text} />
          )}
          <Text style={styles.actionLabel}>
            {pendingImageId ? 'Processing…' : isAddingPhoto ? 'Uploading…' : 'Add photo'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => handleAddPhoto('menu')}
          disabled={isAddingPhoto || !!pendingImageId}
          accessibilityLabel="Add a photo of the menu"
          accessibilityRole="button"
        >
          <Ionicons name="restaurant-outline" size={18} color={Colors.text} />
          <Text style={styles.actionLabel}>Add menu photo</Text>
        </TouchableOpacity>

        {/* Reporting needs a specific photo id, which only exists once the
            detail response carries image_ids. Reports the lead photo —
            the one on the card and the map pin, so the one that actually
            matters if it's wrong. */}
        {place.image_ids?.length ? (
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
              if (!user) {
                toast('Sign in to report a photo');
                return;
              }
              setReportImageId(place.image_ids![0]);
            }}
            accessibilityLabel="Report the main photo"
            accessibilityRole="button"
          >
            <Ionicons name="flag-outline" size={18} color={Colors.textSecondary} />
            <Text style={[styles.actionLabel, { color: Colors.textSecondary }]}>Report</Text>
          </TouchableOpacity>
        ) : null}
      </View>

      {/* Menu */}
      <View style={styles.menuSection}>
        <View style={styles.menuTitleRow}>
          <Text style={styles.sectionTitle}>Menu</Text>
          {/* Previously computed and stored (Place.last_menu_updated_at)
              but never shown — a menu verified yesterday and one untouched
              for eight months rendered identically. */}
          {!menuLoading && menuItems.length > 0 && menuVerifiedAt ? (
            <Text style={styles.menuVerified}>
              Verified {relativeTime(menuVerifiedAt)}
            </Text>
          ) : null}
        </View>
        {menuLoading ? (
          <View style={styles.menuSkeletonWrap}>
            {[1, 2, 3].map((i) => (
              <View key={i} style={{ height: 44, borderRadius: Radius.sm, backgroundColor: Colors.surface }} />
            ))}
          </View>
        ) : menuItems.length === 0 ? (
          <Text style={styles.noMenu}>
            {place.has_menu ? 'Menu coming soon' : 'No menu on file yet'}
          </Text>
        ) : (
          <>
            {Object.entries(menuByCategory).map(([cat, items]) => (
              <View key={cat} style={styles.menuCat}>
                <Text style={styles.menuCatLabel}>{cat}</Text>
                {items.map((item) => (
                  <View key={item.id} style={styles.menuItem}>
                    <View style={styles.menuItemMeta}>
                      <Text style={styles.menuItemName}>{item.name}</Text>
                      {item.description ? (
                        <Text style={styles.menuItemDesc} numberOfLines={2}>
                          {item.description}
                        </Text>
                      ) : null}
                    </View>
                    {item.price != null ? (
                      <Text style={styles.menuItemPrice}>${item.price.toFixed(2)}</Text>
                    ) : null}
                  </View>
                ))}
              </View>
            ))}
            {menuItems.length > 5 && (
              <TouchableOpacity
                style={styles.expandBtn}
                onPress={() => setMenuExpanded((v) => !v)}
                accessibilityRole="button"
                accessibilityLabel={menuExpanded ? 'Show fewer menu items' : `Show all ${menuItems.length} menu items`}
              >
                <Text style={styles.expandLabel}>
                  {menuExpanded ? 'Show less' : `Show all ${menuItems.length} items`}
                </Text>
              </TouchableOpacity>
            )}
          </>
        )}
      </View>

      {/* Seen on social — matched TikTok/YouTube/IG shares. Tapping opens
          the original post; true inline playback would need react-native-webview,
          not currently a dependency, so this links out instead. */}
      {craves.length > 0 && (
        <View style={styles.socialSection}>
          <Text style={styles.sectionTitle}>Seen on social</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.socialRow}>
            {craves.map((item) => (
              <TouchableOpacity
                key={item.id}
                style={styles.socialCard}
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  Linking.openURL(item.url);
                }}
                accessibilityRole="link"
                accessibilityLabel={`Open ${item.source_type} post${item.author_name ? ` by ${item.author_name}` : ''}`}
              >
                {item.thumbnail_url ? (
                  <Image source={{ uri: item.thumbnail_url }} style={styles.socialThumb} />
                ) : (
                  <View style={[styles.socialThumb, styles.socialThumbFallback]}>
                    <Ionicons name="play-circle-outline" size={28} color={Colors.textMuted} />
                  </View>
                )}
                <View style={styles.socialPlatformChip}>
                  <Text style={styles.socialPlatformChipText}>
                    {item.source_type === 'tiktok' ? 'TikTok' : item.source_type === 'youtube' ? 'YouTube' : item.source_type === 'instagram' ? 'Instagram' : 'Link'}
                  </Text>
                </View>
                {item.author_name ? (
                  <Text style={styles.socialAuthor} numberOfLines={1}>@{item.author_name}</Text>
                ) : null}
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      )}

      <ReportPhotoSheet
        visible={reportImageId !== null}
        imageId={reportImageId}
        onClose={() => setReportImageId(null)}
        onReported={() => toast('Thanks — we’ll take a look')}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { paddingBottom: 40 },
  identity: { padding: 16, gap: 5 },
  identityTop: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  price: { color: Colors.textSecondary, fontSize: 13, fontWeight: '600' },
  name: { fontSize: 24, fontWeight: '800', color: Colors.text, letterSpacing: 0.2 },
  meta: { fontSize: 14, color: Colors.textSecondary },
  badgeChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, paddingHorizontal: Spacing.lg, paddingBottom: Spacing.md },
  chip: { paddingHorizontal: 10, paddingVertical: 4, backgroundColor: Colors.border, borderRadius: Radius.pill },
  chipText: { fontSize: 13, color: Colors.textSecondary },
  rankCta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginHorizontal: 16,
    marginTop: 12,
    paddingVertical: 14,
    borderRadius: Radius.pill,
    backgroundColor: Colors.primary,
    minHeight: 50,
  },
  rankCtaText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  rankCtaRanked: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  rankCtaRankedText: { color: Colors.textSecondary, fontSize: 14, fontWeight: '700' },
  rankScoreDot: {
    minWidth: 40,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: Radius.pill,
    borderWidth: 1.5,
    alignItems: 'center',
  },
  rankScoreDotText: { fontSize: 13, fontWeight: '800' },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: Colors.border,
    marginVertical: 8,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    minHeight: 44,
  },
  actionBtnSaved: { borderColor: Colors.primary, backgroundColor: Colors.primary + '22' },
  actionLabel: { color: Colors.text, fontSize: 13, fontWeight: '600' },
  actionLabelSaved: { color: Colors.primary },
  menuSection: { paddingHorizontal: 16, paddingTop: 8 },
  menuTitleRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: Colors.text,
    letterSpacing: 0.3,
  },
  menuVerified: { color: Colors.textMuted, fontSize: 12 },
  noMenu: { color: Colors.textSecondary, fontSize: 14, paddingVertical: 8 },
  menuCat: { marginBottom: 16 },
  menuCatLabel: {
    fontSize: 11,
    fontWeight: '800',
    color: Colors.textMuted,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  menuItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderColor: Colors.border,
  },
  menuItemMeta: { flex: 1 },
  menuItemName: { color: Colors.text, fontSize: 14, fontWeight: '600' },
  menuItemDesc: { color: Colors.textSecondary, fontSize: 12, marginTop: 2 },
  menuItemPrice: {
    color: Colors.textSecondary,
    fontSize: 14,
    fontWeight: '600',
    minWidth: 50,
    textAlign: 'right',
  },
  expandBtn: { marginTop: 8, paddingVertical: 12, alignItems: 'center' },
  expandLabel: { color: Colors.primary, fontSize: 14, fontWeight: '600' },
  menuSkeletonWrap: { gap: Spacing.sm },
  socialSection: { paddingTop: 20, paddingLeft: 16 },
  socialRow: { gap: Spacing.sm, paddingRight: 16, paddingTop: 4 },
  socialCard: { width: 120 },
  socialThumb: {
    width: 120,
    height: 120,
    borderRadius: Radius.md,
    backgroundColor: Colors.surface,
  },
  socialThumbFallback: { alignItems: 'center', justifyContent: 'center' },
  socialPlatformChip: {
    position: 'absolute',
    top: 8,
    left: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: Radius.pill,
    backgroundColor: 'rgba(0,0,0,0.6)',
  },
  socialPlatformChipText: { color: '#fff', fontSize: 10, fontWeight: '700' },
  socialAuthor: { color: Colors.textSecondary, fontSize: 12, marginTop: 6 },
});
