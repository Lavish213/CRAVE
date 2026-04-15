// app/place/[id].tsx
import React, { useCallback, useEffect, useState } from 'react';
import {
  Linking,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useLocalSearchParams, useNavigation } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { fetchPlaceDetail, PlaceOut } from '../../src/api/places';
import { getPlaceMenu, MenuItem } from '../../src/api/menu';
import { useHitlistStore } from '../../src/stores/hitlistStore';
import { useToast } from '../../src/hooks/useToast';
import { Colors, Spacing, Radius } from '../../src/constants/colors';
import { getTier, getSignalContext, getTrustBadges } from '../../src/utils/scoring';
import { ImageGallery } from '../../src/components/ImageGallery';
import { TierBadge } from '../../src/components/TierBadge';
import { TrustBadgeRow } from '../../src/components/TrustBadgeRow';
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
  const { addSave, removeSave, isSaved } = useHitlistStore();
  const toast = useToast((s) => s.show);

  const [place, setPlace] = useState<PlaceOut | null>(null);
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [menuLoading, setMenuLoading] = useState(true);
  const [error, setError] = useState(false);
  const [menuExpanded, setMenuExpanded] = useState(false);

  const handleShare = useCallback(() => {
    if (!place) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    Share.share({
      message: `${place.name} — ${place.category ?? 'Restaurant'}. Found on CRAVE.`,
    });
  }, [place]);

  const load = () => {
    setLoading(true);
    setMenuLoading(true);
    setError(false);
    Promise.all([
      fetchPlaceDetail(id!),
      getPlaceMenu(id!).catch(() => [] as MenuItem[]),
    ])
      .then(([p, m]) => {
        setPlace(p);
        setMenuItems(m);
      })
      .catch(() => setError(true))
      .finally(() => {
        setLoading(false);
        setMenuLoading(false);
      });
  };

  useEffect(() => { if (id) load(); }, [id]);

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

  if (loading) return <DetailSkeleton />;

  if (error || !place) {
    return <ErrorState message="Couldn't load this place" onRetry={load} />;
  }

  const tier = getTier(place.rank_score);
  const context = getSignalContext(place);
  const badges = getTrustBadges(place);
  const saved = isSaved(place.id);
  const allImages = [place.primary_image_url, ...(place.images ?? [])];
  const previewMenu = menuExpanded ? menuItems : menuItems.slice(0, 5);

  // Group menu items by category
  const menuByCategory: Record<string, MenuItem[]> = {};
  for (const item of previewMenu) {
    const cat = item.category ?? 'Menu';
    if (!menuByCategory[cat]) menuByCategory[cat] = [];
    menuByCategory[cat].push(item);
  }

  const handleSave = () => {
    Haptics.notificationAsync(
      saved ? Haptics.NotificationFeedbackType.Warning : Haptics.NotificationFeedbackType.Success,
    );
    if (saved) { removeSave(place.id); toast('Removed from Hitlist'); }
    else { addSave(place); toast('Saved to Hitlist'); }
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
      <ImageGallery images={allImages} />

      {/* Identity */}
      <View style={styles.identity}>
        <View style={styles.identityTop}>
          <TierBadge tier={tier} />
          {place.price_tier ? (
            <Text style={styles.price}>{'$'.repeat(place.price_tier)}</Text>
          ) : null}
        </View>
        <Text style={styles.name}>{place.name}</Text>
        <Text style={styles.meta}>
          {place.category ?? 'Restaurant'}
          {place.address ? `  ·  ${place.address}` : ''}
        </Text>
        <Text style={[styles.context, { color: tier.color }]}>{context}</Text>
      </View>

      {/* Trust badges */}
      <TrustBadgeRow badges={badges} />

      {/* Action row */}
      <View style={styles.actions}>
        <TouchableOpacity
          style={[styles.actionBtn, saved && styles.actionBtnSaved]}
          onPress={handleSave}
          accessibilityLabel={saved ? 'Remove from Hitlist' : 'Save to Hitlist'}
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
      </View>

      {/* Menu */}
      <View style={styles.menuSection}>
        <Text style={styles.sectionTitle}>Menu</Text>
        {menuLoading ? (
          <View style={{ gap: 8 }}>
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
              >
                <Text style={styles.expandLabel}>
                  {menuExpanded ? 'Show less' : `Show all ${menuItems.length} items`}
                </Text>
              </TouchableOpacity>
            )}
          </>
        )}
      </View>
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
  context: { fontSize: 13, fontWeight: '600', marginTop: 2 },
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
  sectionTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: Colors.text,
    marginBottom: 12,
    letterSpacing: 0.3,
  },
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
});
