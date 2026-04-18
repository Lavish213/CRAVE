import React, { useRef } from 'react';
import {
  Animated, Share, StyleSheet, Text, TouchableOpacity, View, ViewStyle,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { PlaceOut } from '../api/places';
import { getTier, formatPrice, getBadges } from '../utils/scoring';
// formatPrice imported for fallback; normalized places already have place.price
import { TierBadge } from './TierBadge';
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
  const price = place.price ?? formatPrice(place);
  const badges = getBadges(place);
  const saveScale = useRef(new Animated.Value(1)).current;

  const handleSave = () => {
    Animated.sequence([
      Animated.timing(saveScale, { toValue: 1.3, duration: 100, useNativeDriver: true }),
      Animated.timing(saveScale, { toValue: 1, duration: 150, useNativeDriver: true }),
    ]).start();
    onSave();
  };

  const categoryLabel = place.category ?? null;
  const distanceLabel = place.distance_miles != null
    ? place.distance_miles < 0.1 ? 'Here'
    : place.distance_miles < 10 ? `${place.distance_miles.toFixed(1)} mi`
    : `${Math.round(place.distance_miles)} mi`
    : null;
  const metaParts = [categoryLabel, price, distanceLabel].filter(Boolean);

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
          message: `${place.name} — ${categoryLabel ?? 'Restaurant'} in ${place.address ? place.address.split(',').pop()?.trim() ?? 'your city' : 'your city'}. Found on CRAVE.`,
        }).catch(() => {});
      }}
      delayLongPress={400}
      activeOpacity={0.85}
      accessibilityRole="button"
      accessibilityLabel={`${place.name}, ${categoryLabel ?? 'Restaurant'}, ${tier.label}`}
    >
      <View style={styles.imageContainer}>
        {place.image ? (
          <Image
            source={place.image}
            style={styles.image}
            contentFit="cover"
            placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
            transition={200}
          />
        ) : (
          <View style={styles.imageFallback}>
            <Text style={styles.imageFallbackInitial}>
              {(place.name || '?')[0].toUpperCase()}
            </Text>
            {categoryLabel && (
              <Text style={styles.imageFallbackCategory}>{categoryLabel}</Text>
            )}
          </View>
        )}
        <View style={styles.scrimBottom} />
        <TierBadge tier={tier} style={styles.tierBadge} />
        <TouchableOpacity
          style={styles.saveBtn}
          onPress={handleSave}
          hitSlop={SAVE_HIT_SLOP}
          activeOpacity={0.7}
          accessibilityLabel={saved ? `Remove ${place.name} from saves` : `Save ${place.name}`}
          accessibilityRole="button"
        >
          <Animated.View style={{ transform: [{ scale: saveScale }] }}>
            <Ionicons name={saved ? 'bookmark' : 'bookmark-outline'} size={20} color={Colors.text} />
          </Animated.View>
        </TouchableOpacity>
      </View>

      <View style={styles.body}>
        <Text style={styles.name} numberOfLines={1}>{place.name}</Text>
        {metaParts.length > 0 && (
          <Text style={styles.meta} numberOfLines={1}>
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
    top: 6,
    right: Spacing.sm,
    padding: 6,
    backgroundColor: 'rgba(0,0,0,0.45)',
    borderRadius: Radius.pill,
  },
  body: { padding: Spacing.lg, paddingTop: Spacing.md, gap: Spacing.xs },
  name: { fontSize: 18, fontWeight: '800', color: Colors.text },
  meta: { fontSize: 13, color: Colors.textSecondary },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 2 },
  chip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    backgroundColor: Colors.border,
    borderRadius: Radius.pill,
  },
  chipText: { fontSize: 12, color: Colors.textSecondary },
  imageFallback: {
    width: '100%',
    height: IMAGE_HEIGHT,
    backgroundColor: Colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  imageFallbackInitial: {
    fontSize: 64,
    fontWeight: '800',
    color: Colors.textMuted,
    lineHeight: 72,
  },
  imageFallbackCategory: {
    fontSize: 13,
    color: Colors.textMuted,
    fontWeight: '500',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
});
