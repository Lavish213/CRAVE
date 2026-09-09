import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, PanResponder, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { CraveIconButton, CraveSheet } from '../ui-v2/primitives';
import { MapPlaceCard } from '../ui-v2/components';
import { uiColors, uiRadius, uiSpace } from '../ui-v2/tokens';

const DISMISS_THRESHOLD = 80;
const DISMISS_VELOCITY = 0.5;
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
  const [reduceMotion, setReduceMotion] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;
    AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (mounted) setReduceMotion(enabled);
    });
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);
    return () => {
      mounted = false;
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    if (feature) translateY.setValue(0);
  }, [feature?.id, translateY]);

  const dismiss = useMemo(
    () => () => {
      if (reduceMotion !== false) {
        translateY.setValue(EXIT_DISTANCE);
        onClose();
        return;
      }
      Animated.timing(translateY, {
        toValue: EXIT_DISTANCE,
        duration: 180,
        useNativeDriver: true,
      }).start(() => onClose());
    },
    [onClose, reduceMotion, translateY],
  );

  const restore = useMemo(
    () => () => {
      if (reduceMotion !== false) {
        translateY.setValue(0);
        return;
      }
      Animated.spring(translateY, {
        toValue: 0,
        useNativeDriver: true,
        bounciness: 4,
      }).start();
    },
    [reduceMotion, translateY],
  );

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_evt, gesture) =>
          gesture.dy > 4 && Math.abs(gesture.dy) > Math.abs(gesture.dx),
        onPanResponderMove: (_evt, gesture) => {
          if (gesture.dy > 0) translateY.setValue(gesture.dy);
        },
        onPanResponderRelease: (_evt, gesture) => {
          if (gesture.dy > DISMISS_THRESHOLD || gesture.vy > DISMISS_VELOCITY) {
            void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
            dismiss();
          } else {
            restore();
          }
        },
        onPanResponderTerminate: restore,
      }),
    [dismiss, restore, translateY],
  );

  if (!feature) return null;

  return (
    <Animated.View
      style={[styles.animatedShell, { transform: [{ translateY }] }]}
      {...panResponder.panHandlers}
    >
      <CraveSheet style={styles.sheet}>
        <View style={styles.grabber} accessibilityElementsHidden importantForAccessibility="no" />
        <CraveIconButton
          accessibilityLabel="Close place preview"
          icon={<Ionicons name="close" size={19} color={uiColors.text.secondary} />}
          onPress={dismiss}
          style={styles.closeButton}
        />
        <MapPlaceCard
          name={feature.name}
          image={feature.image}
          category={feature.category}
          onOpen={() => onOpen(feature.id)}
        />
      </CraveSheet>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  animatedShell: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
  },
  sheet: {
    paddingTop: uiSpace.sm,
    paddingBottom: uiSpace.xxl,
  },
  grabber: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: uiRadius.pill,
    backgroundColor: uiColors.border.strong,
    marginBottom: uiSpace.sm,
  },
  closeButton: {
    position: 'absolute',
    top: uiSpace.sm,
    right: uiSpace.md,
    zIndex: 2,
  },
});
