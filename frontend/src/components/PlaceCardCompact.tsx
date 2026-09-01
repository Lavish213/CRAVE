import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View, ViewStyle } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { PlaceOut } from '../api/places';
import { getTierForPlace, formatPrice, getBadges, percentileCaption, formatDistance } from '../utils/scoring';
// formatPrice imported for fallback; normalized places already have place.price
import { TierBadge } from './TierBadge';
import { Colors, Radius, Shadows } from '../constants/colors';

interface Props {
  place: PlaceOut;
  onPress: () => void;
  /** Fires before onPress -- e.g. to prefetch the destination screen's data. */
  onPressIn?: () => void;
  rightAction?: React.ReactNode;
  style?: ViewStyle;
  /** Per-save memory (E2) -- only meaningful for a Craves list row, so
   * both are optional and undefined elsewhere (Feed/Search/Trending
   * don't have a save's memory to show). Notes content itself is
   * deliberately never shown inline here, only its presence -- see
   * docs/E2_E3_E10_PRODUCT_TRADEOFFS_2026-08-31.md. */
  visited?: boolean;
  hasNotes?: boolean;
}

function PlaceCardCompactImpl({ place, onPress, onPressIn, rightAction, style, visited, hasNotes }: Props) {
  const tier = getTierForPlace(place);
  const price = place.price ?? formatPrice(place);
  const badges = getBadges(place);
  const categoryLabel = place.category ?? null;
  const distanceLabel = formatDistance(place.distance_miles);
  const percentileLabel = percentileCaption(tier, place.rank_percentile);
  const metaParts = [categoryLabel, price, distanceLabel].filter(Boolean);

  return (
    <View style={[styles.shadowWrap, style]}>
    <TouchableOpacity
      style={styles.row}
      onPressIn={onPressIn}
      onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); onPress(); }}
      activeOpacity={0.85}
      accessibilityRole="button"
      accessibilityLabel={`${place.name}, ${categoryLabel ?? 'Restaurant'}, ${tier.label}`}
    >
      {place.image ? (
        <Image
          source={place.image}
          style={styles.thumb}
          contentFit="cover"
          placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
          cachePolicy="memory-disk"
        />
      ) : (
        <View style={styles.thumbFallback}>
          <Text style={styles.thumbFallbackInitial}>
            {(place.name || '?')[0].toUpperCase()}
          </Text>
        </View>
      )}
      <View style={styles.info}>
        <View style={styles.topRow}>
          <TierBadge tier={tier} style={styles.badgeTier} />
          {visited ? (
            <Ionicons
              name="checkmark-circle"
              size={14}
              color={Colors.success}
              accessibilityLabel="Visited"
            />
          ) : null}
          {hasNotes ? (
            <Ionicons
              name="document-text-outline"
              size={13}
              color={Colors.textSecondary}
              accessibilityLabel="Has a note"
            />
          ) : null}
        </View>
        <Text style={styles.name} numberOfLines={1}>{place.name}</Text>
        {percentileLabel ? (
          <Text style={[styles.percentile, { color: tier.color }]}>{percentileLabel}</Text>
        ) : null}
        {metaParts.length > 0 && (
          <Text style={styles.sub} numberOfLines={1}>
            {metaParts.join('  ·  ')}
          </Text>
        )}
        {badges.length > 0 && (
          <View style={styles.badgeRow}>
            {badges.map((b) => (
              <View key={b.label} style={styles.chip}>
                <Text style={styles.chipText}>{b.emoji} {b.label}</Text>
              </View>
            ))}
          </View>
        )}
      </View>
      {rightAction}
    </TouchableOpacity>
    </View>
  );
}

// See PlaceCard.tsx's identical note -- this renders as a FlashList row
// in Search/Craves/TrendingStrip and shouldn't re-render on every parent
// state change unrelated to its own props.
export const PlaceCardCompact = React.memo(PlaceCardCompactImpl);

const styles = StyleSheet.create({
  shadowWrap: {
    borderRadius: Radius.card,
    ...Shadows.card,
  },
  row: {
    flexDirection: 'row',
    gap: 12,
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    overflow: 'hidden',
    alignItems: 'center',
    padding: 10,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  thumb: { width: 64, height: 64, borderRadius: Radius.sm },
  thumbFallback: {
    width: 64,
    height: 64,
    borderRadius: Radius.sm,
    backgroundColor: Colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  thumbFallbackInitial: {
    fontSize: 24,
    fontWeight: '800',
    color: Colors.textSecondary,
  },
  info: { flex: 1, gap: 3 },
  topRow: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  name: { color: Colors.text, fontSize: 15, fontWeight: '600' },
  percentile: { fontSize: 11, fontWeight: '700' },
  sub: { color: Colors.textSecondary, fontSize: 13 },
  badgeTier: { marginBottom: 0 },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 2 },
  chip: {
    paddingHorizontal: 7,
    paddingVertical: 2,
    backgroundColor: Colors.border,
    borderRadius: 10,
  },
  chipText: { fontSize: 11, color: Colors.textSecondary },
});
