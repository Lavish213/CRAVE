// src/components/PlaceCard.tsx
import React from 'react';
import {
  Share, StyleSheet, Text, TouchableOpacity, View, ViewStyle,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { PlaceOut } from '../api/places';
import { getTier, getSignalContext } from '../utils/scoring';
import { TierBadge } from './TierBadge';
import { TrustLine } from './TrustLine';
import { Colors, Spacing, Radius } from '../constants/colors';

const SAVE_HIT_SLOP = { top: 8, bottom: 8, left: 8, right: 8 } as const;
const IMAGE_HEIGHT = 220;

interface Props {
  place: PlaceOut;
  onPress: () => void;
  onSave: () => void;
  saved: boolean;
  style?: ViewStyle;
}

export function PlaceCard({ place, onPress, onSave, saved, style }: Props) {
  const tier = getTier(place.rank_score);
  const context = getSignalContext(place);

  return (
    <TouchableOpacity
      style={[styles.card, style]}
      onPress={() => {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        onPress();
      }}
      onLongPress={() => {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        Share.share({
          message: `${place.name} — ${place.category ?? 'Restaurant'} in ${place.address ? place.address.split(',').pop()?.trim() ?? 'your city' : 'your city'}. Found on CRAVE.`,
        }).catch(() => {});
      }}
      delayLongPress={400}
      activeOpacity={0.85}
      accessibilityRole="button"
      accessibilityLabel={`${place.name}, ${place.category ?? 'Restaurant'}, ${tier.label}`}
    >
      <View style={styles.imageContainer}>
        <Image
          source={place.primary_image_url ?? undefined}
          style={styles.image}
          contentFit="cover"
          placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
          transition={200}
        />
        {/* gradient scrim — two-layer opacity fallback (expo-linear-gradient not installed) */}
        <View style={styles.scrimTop} />
        <View style={styles.scrimBottom} />

        {/* Tier badge — top left */}
        <TierBadge tier={tier} style={styles.tierBadge} />

        {/* Save — top right */}
        <TouchableOpacity
          style={styles.saveBtn}
          onPress={onSave}
          hitSlop={SAVE_HIT_SLOP}
          accessibilityLabel={saved ? `Remove ${place.name} from hitlist` : `Save ${place.name} to hitlist`}
          accessibilityRole="button"
        >
          <Ionicons name={saved ? 'bookmark' : 'bookmark-outline'} size={20} color={Colors.text} />
        </TouchableOpacity>
      </View>

      <View style={styles.body}>
        <Text style={styles.name} numberOfLines={1}>{place.name}</Text>
        <Text style={styles.meta} numberOfLines={1}>
          {place.category ?? 'Restaurant'}
          {place.price_tier ? '  ·  ' + '$'.repeat(place.price_tier) : ''}
        </Text>
        <TrustLine text={context} color={tier.color} />
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  imageContainer: { position: 'relative' },
  image: { width: '100%', height: IMAGE_HEIGHT },
  // Two-layer gradient scrim: transparent top half fading to dark at bottom
  scrimTop: {
    position: 'absolute',
    bottom: 50,
    left: 0,
    right: 0,
    height: 50,
    backgroundColor: 'rgba(0,0,0,0)',
  },
  scrimBottom: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 50,
    backgroundColor: 'rgba(0,0,0,0.75)',
  },
  tierBadge: { position: 'absolute', top: Spacing.sm, left: Spacing.sm },
  saveBtn: {
    position: 'absolute',
    top: 6, // intentional: midpoint between xs(4) and sm(8)
    right: Spacing.sm,
    padding: 6, // intentional: midpoint between xs(4) and sm(8)
    backgroundColor: 'rgba(0,0,0,0.45)',
    borderRadius: Radius.pill,
  },
  body: { padding: Spacing.lg, paddingTop: Spacing.md, gap: Spacing.xs },
  name: { fontSize: 18, fontWeight: '800', color: Colors.text },
  meta: { fontSize: 13, color: Colors.textSecondary },
});
