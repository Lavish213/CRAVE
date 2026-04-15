// src/components/PlaceCardCompact.tsx
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View, ViewStyle } from 'react-native';
import { Image } from 'expo-image';
import * as Haptics from 'expo-haptics';
import { PlaceOut } from '../api/places';
import { getTier, getSignalContext } from '../utils/scoring';
import { TierBadge } from './TierBadge';
import { TrustLine } from './TrustLine';
import { Colors, Radius } from '../constants/colors';

interface Props {
  place: PlaceOut;
  onPress: () => void;
  rightAction?: React.ReactNode;
  style?: ViewStyle;
}

export function PlaceCardCompact({ place, onPress, rightAction, style }: Props) {
  const tier = getTier(place.rank_score);
  const context = getSignalContext(place);

  return (
    <TouchableOpacity
      style={[styles.row, style]}
      onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); onPress(); }}
      activeOpacity={0.85}
      accessibilityRole="button"
      accessibilityLabel={`${place.name}, ${place.category ?? 'Restaurant'}, ${tier.label}`}
    >
      <Image
        source={place.primary_image_url ?? undefined}
        style={styles.thumb}
        contentFit="cover"
        placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
      />
      <View style={styles.meta}>
        <TierBadge tier={tier} style={styles.badgeTier} />
        <Text style={styles.name} numberOfLines={1}>{place.name}</Text>
        <Text style={styles.sub} numberOfLines={1}>
          {place.category ?? 'Restaurant'}
          {place.price_tier ? '  ·  ' + '$'.repeat(place.price_tier) : ''}
        </Text>
        <TrustLine text={context} color={tier.color} />
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
  meta: { flex: 1, gap: 3 },
  name: { color: Colors.text, fontSize: 15, fontWeight: '600' },
  sub: { color: Colors.textSecondary, fontSize: 13 },
  badgeTier: { marginBottom: 2 },
});
