import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View, ViewStyle } from 'react-native';
import { Image } from 'expo-image';
import * as Haptics from 'expo-haptics';
import { PlaceOut } from '../api/places';
import { getTier, formatPrice, getBadges, formatDistance } from '../utils/scoring';
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
}

function PlaceCardCompactImpl({ place, onPress, onPressIn, rightAction, style }: Props) {
  const tier = getTier(place.rank_score);
  const price = place.price ?? formatPrice(place);
  const badges = getBadges(place);
  const categoryLabel = place.category ?? null;
  const distanceLabel = formatDistance(place.distance_miles);
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
        <TierBadge tier={tier} style={styles.badgeTier} />
        <Text style={styles.name} numberOfLines={1}>{place.name}</Text>
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
    color: Colors.textMuted,
  },
  info: { flex: 1, gap: 3 },
  name: { color: Colors.text, fontSize: 15, fontWeight: '600' },
  sub: { color: Colors.textSecondary, fontSize: 13 },
  badgeTier: { marginBottom: 2 },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 2 },
  chip: {
    paddingHorizontal: 7,
    paddingVertical: 2,
    backgroundColor: Colors.border,
    borderRadius: 10,
  },
  chipText: { fontSize: 11, color: Colors.textSecondary },
});
