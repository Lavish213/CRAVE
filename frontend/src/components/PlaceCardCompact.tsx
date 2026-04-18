import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View, ViewStyle } from 'react-native';
import { Image } from 'expo-image';
import * as Haptics from 'expo-haptics';
import { PlaceOut } from '../api/places';
import { getTier, formatPrice, getBadges } from '../utils/scoring';
// formatPrice imported for fallback; normalized places already have place.price
import { TierBadge } from './TierBadge';
import { Colors, Radius } from '../constants/colors';

interface Props {
  place: PlaceOut;
  onPress: () => void;
  rightAction?: React.ReactNode;
  style?: ViewStyle;
}

export function PlaceCardCompact({ place, onPress, rightAction, style }: Props) {
  const tier = getTier(place.rank_score);
  const price = place.price ?? formatPrice(place);
  const badges = getBadges(place);
  const categoryLabel = place.category ?? null;
  const distanceLabel = place.distance_miles != null
    ? place.distance_miles < 0.1 ? 'Here'
    : place.distance_miles < 10 ? `${place.distance_miles.toFixed(1)} mi`
    : `${Math.round(place.distance_miles)} mi`
    : null;
  const metaParts = [categoryLabel, price, distanceLabel].filter(Boolean);

  return (
    <TouchableOpacity
      style={[styles.row, style]}
      onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); onPress(); }}
      activeOpacity={0.85}
      accessibilityRole="button"
      accessibilityLabel={`${place.name}, ${categoryLabel ?? 'Restaurant'}, ${tier.label}`}
    >
      <Image
        source={place.image ?? undefined}
        style={styles.thumb}
        contentFit="cover"
        placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
      />
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
  );
}

const styles = StyleSheet.create({
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
