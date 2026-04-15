import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View, ViewStyle } from 'react-native';
import { Colors, Radius, Spacing } from '../constants/colors';

function Shimmer({ style }: { style?: ViewStyle }) {
  const opacity = useRef(new Animated.Value(0.3)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, {
          toValue: 0.7,
          duration: 800,
          useNativeDriver: true,
        }),
        Animated.timing(opacity, {
          toValue: 0.3,
          duration: 800,
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);

  return (
    <Animated.View
      style={[styles.shimmer, style, { opacity }]}
    />
  );
}

export function SkeletonCard() {
  return (
    <View style={styles.card}>
      {/* Image placeholder */}
      <Shimmer style={styles.image} />
      {/* Badge placeholder */}
      <View style={styles.body}>
        <Shimmer style={styles.badge} />
        <Shimmer style={styles.title} />
        <Shimmer style={styles.meta} />
        <Shimmer style={styles.context} />
      </View>
    </View>
  );
}

export function SkeletonFeed({ count = 3 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.sm,
  },
  shimmer: {
    backgroundColor: Colors.surfaceElevated,
    borderRadius: Radius.sm,
  },
  image: {
    width: '100%',
    height: 220,
    borderRadius: 0,
  },
  body: {
    padding: Spacing.lg,
    paddingTop: Spacing.md,
    gap: Spacing.sm,
  },
  badge: {
    width: 72,
    height: 14,
    borderRadius: 4,
  },
  // name row — matches 18px/800 font
  title: {
    width: '65%',
    height: 20,
  },
  // meta row — category · price
  meta: {
    width: '45%',
    height: 13,
  },
  // trust line row
  context: {
    width: '80%',
    height: 12,
  },
});
