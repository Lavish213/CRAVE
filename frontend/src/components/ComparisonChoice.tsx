// src/components/ComparisonChoice.tsx
//
// One side of a "which was better?" head-to-head.
//
// Deliberately tap-to-choose rather than Tinder-style swipe-to-dismiss.
// A swipe reads as accept/reject of the *one* thing on screen; this is a
// choice *between two* things, both of which stay. The Tinder lessons that
// do carry over are the ones that matter: visual-first (the photo is the
// card, not a thumbnail beside text), a strictly binary decision with no
// third option to deliberate over, and immediate physical feedback on
// commit so the choice feels registered.
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import { Colors, Radius, Spacing } from '../constants/colors';

interface Props {
  name: string;
  imageUrl?: string | null;
  category?: string | null;
  /** Shown as a small corner tag, e.g. "Your #3" for an already-ranked place. */
  badge?: string | null;
  onChoose: () => void;
  disabled?: boolean;
}

export function ComparisonChoice({
  name,
  imageUrl,
  category,
  badge,
  onChoose,
  disabled,
}: Props) {
  const handlePress = () => {
    if (disabled) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onChoose();
  };

  return (
    <Pressable
      onPress={handlePress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={`Choose ${name} as the better one`}
      style={({ pressed }) => [
        styles.card,
        pressed && !disabled ? styles.cardPressed : null,
        disabled ? styles.cardDisabled : null,
      ]}
    >
      {imageUrl ? (
        <Image
          source={imageUrl}
          style={StyleSheet.absoluteFill}
          contentFit="cover"
          transition={150}
          placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
        />
      ) : (
        <View style={[StyleSheet.absoluteFill, styles.fallback]}>
          <Ionicons name="restaurant" size={36} color={Colors.textMuted} />
        </View>
      )}

      {/* Text sits on top of a photo, so it needs its own contrast floor
          rather than relying on whatever the image happens to be. */}
      <LinearGradient
        colors={['transparent', 'rgba(0,0,0,0.85)']}
        style={styles.scrim}
        pointerEvents="none"
      />

      {badge ? (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{badge}</Text>
        </View>
      ) : null}

      <View style={styles.meta}>
        <Text style={styles.name} numberOfLines={2}>
          {name}
        </Text>
        {category ? (
          <Text style={styles.category} numberOfLines={1}>
            {category}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    borderRadius: Radius.card,
    overflow: 'hidden',
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    justifyContent: 'flex-end',
    minHeight: 140,
  },
  cardPressed: {
    borderColor: Colors.primary,
    transform: [{ scale: 0.98 }],
  },
  cardDisabled: { opacity: 0.5 },
  fallback: {
    backgroundColor: Colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scrim: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: '60%',
  },
  badge: {
    position: 'absolute',
    top: Spacing.sm,
    left: Spacing.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: Radius.pill,
    backgroundColor: 'rgba(0,0,0,0.6)',
  },
  badgeText: { color: Colors.text, fontSize: 11, fontWeight: '800' },
  meta: { padding: Spacing.md },
  name: { color: Colors.text, fontSize: 18, fontWeight: '800' },
  category: { color: Colors.textSecondary, fontSize: 13, marginTop: 2 },
});
