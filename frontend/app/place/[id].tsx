// app/place/[id].tsx
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Image } from 'expo-image';
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
import { getTierForPlace, formatPrice, formatDistance, computeDistanceMiles } from '../../src/utils/scoring';
import { fetchMyRankings, fetchFriendRankings, FriendRanking } from '../../src/api/social';
import { formatScore, tierColor, TIER_LABELS } from '../../src/utils/rankScore';
import { relativeTime } from '../../src/utils/time';
import { useLocation } from '../../src/hooks/useLocation';
import { useCityStore } from '../../src/stores/cityStore';
import { withImageWidth, AVATAR_IMAGE_WIDTH } from '../../src/utils/imageUrl';
import { ImageGallery } from '../../src/components/ImageGallery';
import { PlaceVideoGallery } from '../../src/components/PlaceVideoGallery';
import { ReportPhotoSheet } from '../../src/components/ReportPhotoSheet';
import { MenuSubmissionSheet } from '../../src/components/MenuSubmissionSheet';
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
  const userLocation = useLocation();
  const cities = useCityStore((s) => s.cities);

  const { data: place, isLoading, isError, error, refetch } = useQuery({
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
  const [menuSubmitVisible, setMenuSubmitVisible] = useState(false);

  const [isAddingPhoto, setIsAddingPhoto] = useState(false);
  const [pendingImageId, setPendingImageId] = useState<string | undefined>();
  const { status: uploadStatus, error: uploadError, moderationStatus } = useImageStatusPoll(pendingImageId);

  useEffect(() => {
    if (!pendingImageId || !uploadStatus) return;
    if (uploadStatus === 'ready') {
      // `status: "ready"` only means processing finished -- it says
      // nothing about whether the photo actually went live. A held photo
      // still fully processes; check moderationStatus separately or this
      // reads as "Photo added" for a photo the uploader can't actually
      // see yet, sitting hidden pending review.
      if (moderationStatus === 'pending_review') {
        toast("Submitted for review — we'll let you know");
      } else if (moderationStatus === 'rejected') {
        toast("Your photo wasn't approved");
      } else {
        toast('Photo added');
      }
      setPendingImageId(undefined);
      refetch();
    } else if (uploadStatus === 'failed') {
      toast(uploadError ?? 'Photo failed to process');
      setPendingImageId(undefined);
    }
  }, [uploadStatus, uploadError, moderationStatus, pendingImageId, toast, refetch]);

  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [menuVerifiedAt, setMenuVerifiedAt] = useState<string | null>(null);
  const [menuLoading, setMenuLoading] = useState(true);
  const [menuExpanded, setMenuExpanded] = useState(false);

  // expo-router can reuse this screen instance across a param change (e.g.
  // tapping from one place's menu/social content into another place's
  // detail) rather than unmounting — without a guard, a slow response for
  // the *previous* place's id could resolve after the new place's and
  // silently overwrite this screen with the wrong place's menu/craves. Each
  // fetch below gets its own counter since they're independent requests —
  // sharing one would make each falsely invalidate the other on mount.
  const menuGenerationRef = useRef(0);

  // Fetch menu separately (not worth a useQuery for this small side-load)
  useEffect(() => {
    if (!id) return;
    const myGeneration = ++menuGenerationRef.current;
    setMenuLoading(true);
    getPlaceMenu(id)
      .then((m) => {
        if (myGeneration !== menuGenerationRef.current) return;
        setMenuItems(m.items);
        setMenuVerifiedAt(m.lastVerifiedAt);
      })
      .catch(() => {
        if (myGeneration !== menuGenerationRef.current) return;
        setMenuItems([]);
        setMenuVerifiedAt(null);
      })
      .finally(() => {
        if (myGeneration !== menuGenerationRef.current) return;
        setMenuLoading(false);
      });
  }, [id]);

  const [craves, setCraves] = useState<CraveItem[]>([]);
  const cravesGenerationRef = useRef(0);

  // Matched shares for this place — "seen on TikTok/YouTube" social proof.
  // Public endpoint, no auth needed, silently empty on failure (this is
  // supplementary content, not worth an error state of its own). Unlike the
  // menu fetch above, there's no loading flag gating this section's
  // visibility (it renders whenever craves.length > 0) — without resetting
  // craves here, place A's rows (each a tap target to A's matched place)
  // would stay visibly attributed to place B's screen for as long as B's
  // fetch is in flight.
  useEffect(() => {
    if (!id) return;
    const myGeneration = ++cravesGenerationRef.current;
    setCraves([]);
    getCravesForPlace(id)
      .then((items) => {
        if (myGeneration !== cravesGenerationRef.current) return;
        setCraves(items);
      })
      .catch(() => {
        if (myGeneration !== cravesGenerationRef.current) return;
        setCraves([]);
      });
  }, [id]);

  const [friendRankings, setFriendRankings] = useState<FriendRanking[]>([]);
  const friendRankingsGenerationRef = useRef(0);

  // "X of your friends ranked this" — the direct equivalent of Beli's
  // friend-rating feature. Authenticated (needs the caller's own follow
  // graph), so only fetched when signed in — silently empty otherwise,
  // same "supplementary content, not worth its own error state" treatment
  // as the craves/social fetch above.
  useEffect(() => {
    if (!id || !user) {
      setFriendRankings([]);
      return;
    }
    const myGeneration = ++friendRankingsGenerationRef.current;
    setFriendRankings([]);
    fetchFriendRankings(id)
      .then((rankings) => {
        if (myGeneration !== friendRankingsGenerationRef.current) return;
        setFriendRankings(rankings);
      })
      .catch(() => {
        if (myGeneration !== friendRankingsGenerationRef.current) return;
        setFriendRankings([]);
      });
  }, [id, user]);

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
    // No response at all (vs. a real 4xx/5xx) means the request never
    // reached the backend -- same "genuinely offline" signal cravesStore's
    // _classifyError already uses elsewhere, applied here since this
    // screen previously showed the identical generic message for both.
    const isOffline = !(error as any)?.response;
    return (
      <ErrorState
        message={isOffline ? "Can't reach CRAVE — check your connection." : "Couldn't load this place"}
        onRetry={() => refetch()}
      />
    );
  }

  const tier = getTierForPlace(place);
  const price = place.price ?? formatPrice(place);
  const saved = isSaved(place.id);
  const allImages: string[] = place.images?.length ? place.images : (place.image ? [place.image] : []);
  const previewMenu = menuExpanded ? menuItems : menuItems.slice(0, 5);

  // Place Detail's GET /place/{id} takes no lat/lng, so place.distance_miles
  // (populated server-side on Feed/Search, which do send them) is always
  // null here -- compute it client-side instead of just omitting distance.
  const distanceMiles =
    userLocation && place.lat != null && place.lng != null
      ? computeDistanceMiles(userLocation.lat, userLocation.lng, place.lat, place.lng)
      : place.distance_miles;
  const distanceLabel = formatDistance(distanceMiles);
  const cityName = cities.find((c) => c.id === place.city_id)?.name ?? null;

  // "Why this fits" -- the one section whose whole job is to answer "why
  // THIS place," using only signals that are actually real today (no
  // fabricated match %, see CRAVE_PLACE_DETAIL_SPEC.md §2). The catalog
  // standing line only claims a percentile when one actually exists.
  const percentileHeadline =
    place.rank_percentile != null
      ? `${tier.label} — top ${Math.max(1, Math.round((1 - place.rank_percentile) * 100))}%${cityName ? ` in ${cityName}` : ''}`
      : tier.label;
  const topFriendRanking = friendRankings[0] ?? null;
  // A cold-start place (no percentile snapshot yet, no friend signal)
  // reduces this section to the bare tier word alone -- "Explore" in a
  // box, on its own, isn't an explanation of anything and reads as
  // padding. Suppress the section rather than show near-empty signal;
  // this matches how friend rankings/craves already go silent instead of
  // padding with a fake claim when there's genuinely nothing to show.
  const hasWhyFitsSignal = place.rank_percentile != null || topFriendRanking != null;

  // Group menu items by category
  const menuByCategory: Record<string, MenuItem[]> = {};
  for (const item of previewMenu) {
    const cat = item.category ?? 'Menu';
    if (!menuByCategory[cat]) menuByCategory[cat] = [];
    menuByCategory[cat].push(item);
  }

  const handleSave = async () => {
    if (!user) return;
    const saveMeta = {
      surface: 'place_detail' as const,
      rank_percentile: place.rank_percentile,
      city_id: place.city_id ?? null,
    };
    if (saved) {
      const err = await removeSave(place.id, user.id, saveMeta);
      if (err) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
        toast(err);
      } else {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
        toast('Removed from Saves');
      }
    } else {
      const err = await addSave(place, user.id, saveMeta);
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

  const handleOpenMenuSubmit = () => {
    if (!user) {
      toast('Sign in to suggest menu items');
      return;
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setMenuSubmitVisible(true);
  };

  const handleDirections = () => {
    if (!place.lat || !place.lng) return;
    const mapsUrl = `maps://?q=${encodeURIComponent(place.name)}&ll=${place.lat},${place.lng}`;
    const webUrl = `https://maps.google.com/?q=${place.lat},${place.lng}`;
    Linking.canOpenURL(mapsUrl)
      .then((ok) => Linking.openURL(ok ? mapsUrl : webUrl))
      .catch(() => toast("Couldn't open Maps."));
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Hero gallery */}
      <ImageGallery
        images={allImages}
        gpsVerified={place.images?.length ? place.image_gps_verified : undefined}
        placeName={place.name}
      />

      {/* Food videos */}
      <PlaceVideoGallery placeId={place.id} />

      {/* Identity — name leads, tier judgment follows (was reversed before:
          badge/price came first, name second). */}
      <View style={styles.identity}>
        <Text style={styles.name} accessibilityRole="header">{place.name}</Text>
        <View style={styles.identityTop}>
          <TierBadge tier={tier} />
        </View>
        {(place.category || place.address) ? (
          <Text style={styles.meta}>
            {[place.category, place.address].filter(Boolean).join('  ·  ')}
          </Text>
        ) : null}
      </View>

      {/* Decision strip — the facts that gate whether this is even viable
          right now. Deliberately no open/closed indicator: Place has no
          hours/is_open field at all today, and a guessed or stale "open
          now" is worse than none (see CRAVE_PLACE_DETAIL_SPEC.md §3.2 —
          logged as a real backend gap, not faked here). */}
      {(price || distanceLabel || (place.lat && place.lng)) ? (
        <View style={styles.decisionStrip}>
          {price ? (
            <View accessible accessibilityLabel={`Price: ${price}`}>
              <Text style={styles.decisionChip} importantForAccessibility="no">💰 {price}</Text>
            </View>
          ) : null}
          {distanceLabel ? (
            <View accessible accessibilityLabel={`Distance: ${distanceLabel}`}>
              <Text style={styles.decisionChip} importantForAccessibility="no">📍 {distanceLabel}</Text>
            </View>
          ) : null}
          {place.lat && place.lng ? (
            <TouchableOpacity
              style={styles.decisionChipTouchable}
              hitSlop={{ top: 10, bottom: 10, left: 8, right: 8 }}
              onPress={() => {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                handleDirections();
              }}
              accessibilityRole="button"
              accessibilityLabel="Get directions"
            >
              <Text style={[styles.decisionChip, styles.decisionChipLink]}>🔗 Directions</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      ) : null}

      {/* "Why this fits" — the section that actually answers "why THIS
          place," synthesized from signals CRAVE genuinely has today: the
          catalog percentile (never phrased as personalization) and real
          friend rankings. No taste-match %, no "you tend to like X" — no
          user taste graph exists yet (Decision Intelligence doctrine
          Gate 2). See CRAVE_PLACE_DETAIL_SPEC.md §3.3/§2. Suppressed
          entirely (not shown half-empty) when there's no real signal
          yet — see hasWhyFitsSignal above. */}
      {hasWhyFitsSignal && (
      <View style={styles.whyFits}>
        <Text
          style={[styles.whyFitsHeadline, { color: tier.color }]}
          accessibilityRole="header"
        >
          {percentileHeadline}
        </Text>
        {topFriendRanking ? (
          <Text style={styles.whyFitsFriends}>
            {friendRankings.length === 1
              ? `${topFriendRanking.username} ranked this ${formatScore(topFriendRanking.rank_score)}/10`
              : `${friendRankings.length} friends ranked this — ${topFriendRanking.username} gave it ${formatScore(topFriendRanking.rank_score)}/10`}
          </Text>
        ) : null}
        {friendRankings.length > 1 && (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.socialRow}>
            {friendRankings.map((r) => (
              <TouchableOpacity
                key={r.user_id}
                style={styles.friendRankCard}
                onPress={() => router.push(`/user/${r.user_id}`)}
                accessibilityRole="link"
                accessibilityLabel={`View ${r.username}'s profile — ranked ${TIER_LABELS[r.tier]}`}
              >
                {r.avatar_url ? (
                  <Image
                    source={withImageWidth(r.avatar_url, AVATAR_IMAGE_WIDTH)}
                    style={styles.friendRankAvatar}
                    contentFit="cover"
                    cachePolicy="memory-disk"
                  />
                ) : (
                  <View style={[styles.friendRankAvatar, styles.friendRankAvatarFallback]}>
                    <Ionicons name="person" size={18} color={Colors.textSecondary} />
                  </View>
                )}
                <Text style={styles.friendRankUsername} numberOfLines={1}>@{r.username}</Text>
                <Text style={[styles.friendRankTier, { color: tierColor(r.tier) }]}>
                  {TIER_LABELS[r.tier]}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        )}
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
          style={[styles.actionBtn, styles.actionBtnSave, saved && styles.actionBtnSaved]}
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
              Linking.openURL(place.website!).catch(() => toast("Couldn't open that website."));
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
              Linking.openURL(place.grubhub_url!).catch(() => toast("Couldn't open that link."));
            }}
            accessibilityLabel="Order online"
            accessibilityRole="link"
          >
            <Ionicons name="restaurant-outline" size={18} color={Colors.text} />
            <Text style={styles.actionLabel}>Order</Text>
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

      {/* What to get — promoted from a collapsible list near the bottom to
          a visually prominent section (CRAVE_PLACE_DETAIL_SPEC.md §3.5).
          Same data/logic as before; no dish-level "recommended for you"
          claim added — no dish-affinity model exists. */}
      <View style={styles.menuSection}>
        <View style={styles.menuTitleRow}>
          <Text style={styles.sectionTitle} accessibilityRole="header">What to get</Text>
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
                  <View
                    key={item.id}
                    style={styles.menuItem}
                    accessible
                    accessibilityLabel={
                      `${item.name}` +
                      (item.description ? `, ${item.description}` : '') +
                      (item.price != null ? `, $${item.price.toFixed(2)}` : '')
                    }
                  >
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

        {!menuLoading && (
          <TouchableOpacity
            style={styles.suggestMenuBtn}
            onPress={handleOpenMenuSubmit}
            accessibilityRole="button"
            accessibilityLabel="Suggest menu items"
          >
            <Ionicons name="create-outline" size={16} color={Colors.primary} />
            <Text style={styles.suggestMenuText}>
              {menuItems.length === 0 ? 'Add menu items' : 'Suggest a correction'}
            </Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Seen on social — matched TikTok/YouTube/IG shares. Lower-trust
          public UGC (no curation, unlike the friend-ranking signal folded
          into "Why this fits" above), so it lives here in progressive
          disclosure rather than as competing above-the-fold social proof.
          Tapping opens the original post; true inline playback would need
          react-native-webview, not currently a dependency, so this links
          out instead. */}
      {craves.length > 0 && (
        <View style={styles.socialSection}>
          <Text style={styles.sectionTitle} accessibilityRole="header">Seen on social</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.socialRow}>
            {craves.map((item) => (
              <TouchableOpacity
                key={item.id}
                style={styles.socialCard}
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  Linking.openURL(item.url).catch(() => toast("Couldn't open that post."));
                }}
                accessibilityRole="link"
                accessibilityLabel={`Open ${item.source_type} post${item.author_name ? ` by ${item.author_name}` : ''}`}
              >
                {item.thumbnail_url ? (
                  <Image
                    source={withImageWidth(item.thumbnail_url, AVATAR_IMAGE_WIDTH)}
                    style={styles.socialThumb}
                    contentFit="cover"
                    cachePolicy="memory-disk"
                  />
                ) : (
                  <View style={[styles.socialThumb, styles.socialThumbFallback]}>
                    <Ionicons name="play-circle-outline" size={28} color={Colors.textSecondary} />
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

      <MenuSubmissionSheet
        visible={menuSubmitVisible}
        placeId={place.id}
        onClose={() => setMenuSubmitVisible(false)}
        onSubmitted={() => toast('Thanks — submitted for review')}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { paddingBottom: 40 },
  // More top padding than the old 16px -- the hero photo/video should
  // read as the anchor, with a real beat of whitespace before identity
  // starts, not identity crowding directly against the last frame.
  identity: { paddingHorizontal: 16, paddingTop: Spacing.xl, paddingBottom: 8, gap: 6 },
  identityTop: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  price: { color: Colors.textSecondary, fontSize: 13, fontWeight: '600' },
  // 26/900, up from 24/800 -- the one piece of text on this screen that
  // should out-weigh everything below it typographically.
  name: { fontSize: 26, fontWeight: '900', color: Colors.text, letterSpacing: 0.1 },
  meta: { fontSize: 14, color: Colors.textSecondary },
  decisionStrip: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 14,
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingBottom: 12,
  },
  decisionChip: { fontSize: 14, color: Colors.textSecondary, fontWeight: '600' },
  decisionChipLink: { color: Colors.primary },
  // Explicit min touch target -- unlike Text's own bounds, which shrink to
  // the glyphs and would otherwise fall well under the 44pt minimum every
  // other button on this screen already meets.
  decisionChipTouchable: { minHeight: 44, minWidth: 44, justifyContent: 'center' },
  // No border/background -- this was one of several near-identical
  // bordered boxes stacked down the screen (this, every menu item, every
  // action button), each competing for the same visual weight instead of
  // one of them actually reading as more important. Typography (a larger,
  // tier-colored headline) carries the signal instead of a card.
  whyFits: {
    marginHorizontal: 16,
    marginBottom: 8,
    gap: 6,
  },
  whyFitsHeadline: { fontSize: 18, fontWeight: '800' },
  whyFitsFriends: { fontSize: 13, color: Colors.textSecondary },
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
  // Plain icon+label, no border/background -- Website/Order/Add photo/
  // Add menu photo/Report were all individually boxed pills, identical
  // in weight to Save, competing with it and with every menu item box
  // below. Only Save (below) keeps a bordered pill now, because its
  // saved/unsaved state is a real selection signal worth the visual
  // weight -- everything else here is a plain secondary action.
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 10,
    minHeight: 44,
  },
  actionBtnSave: {
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    paddingHorizontal: 14,
  },
  actionBtnSaved: { borderColor: Colors.primary, backgroundColor: Colors.primary + '22' },
  actionLabel: { color: Colors.textSecondary, fontSize: 13, fontWeight: '600' },
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
  menuVerified: { color: Colors.textSecondary, fontSize: 12 },
  noMenu: { color: Colors.textSecondary, fontSize: 14, paddingVertical: 8 },
  menuCat: { marginBottom: 16 },
  menuCatLabel: {
    fontSize: 11,
    fontWeight: '800',
    color: Colors.textSecondary,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  // A hairline divider, not an individually boxed card -- every item
  // previously got its own bordered/filled rounded rectangle, which
  // reads as 5-20 near-identical cards stacked in a row rather than one
  // coherent list. The name/price sizing already carries "this is a
  // promoted section" (see CRAVE_PLACE_DETAIL_SPEC.md §3.5); it doesn't
  // also need a box around every line to read that way.
  menuItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderColor: Colors.border,
  },
  menuItemMeta: { flex: 1 },
  menuItemName: { color: Colors.text, fontSize: 15, fontWeight: '700' },
  menuItemDesc: { color: Colors.textSecondary, fontSize: 13, marginTop: 3 },
  menuItemPrice: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '700',
    minWidth: 50,
    textAlign: 'right',
  },
  expandBtn: { marginTop: 8, paddingVertical: 12, alignItems: 'center' },
  expandLabel: { color: Colors.primary, fontSize: 14, fontWeight: '600' },
  suggestMenuBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: 8,
    paddingVertical: 12,
  },
  suggestMenuText: { color: Colors.primary, fontSize: 14, fontWeight: '600' },
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
  friendRankCard: { width: 84, alignItems: 'center' },
  friendRankAvatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: Colors.surface,
  },
  friendRankAvatarFallback: { alignItems: 'center', justifyContent: 'center' },
  friendRankUsername: {
    color: Colors.text,
    fontSize: 12,
    fontWeight: '600',
    marginTop: 6,
    maxWidth: 84,
  },
  friendRankTier: { fontSize: 11, fontWeight: '700', marginTop: 2 },
});
