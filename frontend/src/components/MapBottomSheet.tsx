// src/components/MapBottomSheet.tsx
//
// The map's place card. Modeled on Google Maps' persistent sheet: it sits
// over a still-interactive map and is dismissed by dragging it down, not
// only by hunting for a close button.
//
// Drag uses the threshold-gated commit pattern — past DISMISS_THRESHOLD the
// sheet animates the rest of the way out and closes; short of it, it springs
// back. Downward-only: there's no expanded state to drag up into, since
// tapping the card opens the full place screen rather than growing the sheet.
//
// PanResponder + Animated rather than react-native-gesture-handler here:
// this is a single-axis drag on one element, and RN's built-in responder
// needs no GestureHandlerRootView provider at the app root to work.
import React, { useEffect, useMemo, useRef } from 'react';
import { Animated, PanResponder, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { Colors, Radius, Spacing } from '../constants/colors';
import { TierBadge } from './TierBadge';
import { TIERS } from '../utils/scoring';
import type { TierKey } from '../utils/scoring';

// Map GeoJSON tier strings to TierKey
const TIER_MAP: Record<string, TierKey> = {
  elite:   'crave_pick',
  trusted: 'gem',
  solid:   'solid',
  default: 'new',
};

/** Drag distance past which releasing dismisses instead of springing back. */
const DISMISS_THRESHOLD = 80;
/** A fast flick dismisses even if it hasn't travelled the full threshold. */
const DISMISS_VELOCITY = 0.5;
/** Far enough to clear the sheet's own height on the way out. */
const EXIT_DISTANCE = 400;

interface FeatureProps {
  id: string;
  name: string;
  tier: string;
  image?: string;
  category?: string;
}

interface Props {
  feature: FeatureProps | null;
  onOpen: (id: string) => void;
  onClose: () => void;
}

export function MapBottomSheet({ feature, onOpen, onClose }: Props) {
  const translateY = useRef(new Animated.Value(0)).current;

  // Reset position whenever a new feature is selected — otherwise a sheet
  // dismissed by dragging would reopen still translated off-screen.
  useEffect(() => {
    if (feature) translateY.setValue(0);
  }, [feature?.id, translateY]);

  const dismiss = useMemo(
    () => () => {
      Animated.timing(translateY, {
        toValue: EXIT_DISTANCE,
        duration: 180,
        useNativeDriver: true,
      }).start(() => onClose());
    },
    [translateY, onClose],
  );

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        // Claim the gesture only once it's clearly a deliberate downward
        // drag, so taps on the card still reach the button underneath.
        onMoveShouldSetPanResponder: (_evt, gesture) =>
          gesture.dy > 4 && Math.abs(gesture.dy) > Math.abs(gesture.dx),
        onPanResponderMove: (_evt, gesture) => {
          if (gesture.dy > 0) translateY.setValue(gesture.dy);
        },
        onPanResponderRelease: (_evt, gesture) => {
          if (gesture.dy > DISMISS_THRESHOLD || gesture.vy > DISMISS_VELOCITY) {
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
            dismiss();
          } else {
            Animated.spring(translateY, {
              toValue: 0,
              useNativeDriver: true,
              bounciness: 4,
            }).start();
          }
        },
        onPanResponderTerminate: () => {
          Animated.spring(translateY, {
            toValue: 0,
            useNativeDriver: true,
            bounciness: 4,
          }).start();
        },
      }),
    [translateY, dismiss],
  );

  if (!feature) return null;

  const tierKey: TierKey = TIER_MAP[feature.tier] ?? 'new';
  const tier = TIERS[tierKey];

  return (
    <Animated.View
      style={[styles.sheet, { transform: [{ translateY }] }]}
      {...panResponder.panHandlers}
    >
      {/* Grabber: the affordance that says "this can be dragged". Without
          it the drag is undiscoverable even though it works. */}
      <View style={styles.grabber} />

      <TouchableOpacity
        style={styles.closeBtn}
        onPress={dismiss}
        accessibilityLabel="Close"
        accessibilityRole="button"
      >
        <Ionicons name="close" size={18} color={Colors.textMuted} />
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.row}
        onPress={() => onOpen(feature.id)}
        activeOpacity={0.85}
        accessibilityRole="button"
        accessibilityLabel={`Open ${feature.name}`}
      >
        {feature.image ? (
          <Image
            source={feature.image}
            style={styles.thumb}
            contentFit="cover"
            placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
          />
        ) : (
          <View style={[styles.thumb, styles.thumbFallback]}>
            <Ionicons name="restaurant" size={24} color={Colors.textMuted} />
          </View>
        )}
        <View style={styles.meta}>
          <TierBadge tier={tier} />
          <Text style={styles.name} numberOfLines={1}>{feature.name}</Text>
          {feature.category ? (
            <Text style={styles.category}>{feature.category}</Text>
          ) : null}
        </View>
        <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
      </TouchableOpacity>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: Colors.surface,
    borderTopLeftRadius: Radius.pill,
    borderTopRightRadius: Radius.pill,
    padding: Spacing.lg,
    paddingBottom: Spacing.xxl,
    borderTopWidth: 1,
    borderColor: Colors.border,
    shadowColor: '#000',
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: -4 },
    elevation: 16,
  },
  grabber: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: Colors.border,
    marginBottom: Spacing.sm,
    marginTop: -Spacing.sm,
  },
  closeBtn: {
    position: 'absolute',
    top: Spacing.md,
    right: Spacing.lg,
    padding: 6,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md, marginTop: Spacing.sm },
  thumb: { width: 60, height: 60, borderRadius: Radius.sm },
  thumbFallback: {
    backgroundColor: Colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  meta: { flex: 1, gap: Spacing.xs },
  name: { color: Colors.text, fontSize: 16, fontWeight: '700' },
  category: { color: Colors.textSecondary, fontSize: 13 },
});
