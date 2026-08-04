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

/**
 * The compact-row counterpart to SkeletonCard — for screens whose primary
 * loading state was still a centered ActivityIndicator (Profile's ranked
 * list, Leaderboard, Friends feed): a thumb/avatar plus one or two text
 * bars, matching PlaceCardCompact / RankedPlaceRow's actual row shape so
 * the loading state doesn't jump when real content replaces it.
 */
export function SkeletonRow({ avatar = false }: { avatar?: boolean }) {
  return (
    <View style={styles.row}>
      <Shimmer style={avatar ? styles.rowAvatar : styles.rowThumb} />
      <View style={styles.rowBody}>
        <Shimmer style={styles.rowTitle} />
        <Shimmer style={styles.rowMeta} />
      </View>
    </View>
  );
}

export function SkeletonRowList({ count = 5, avatar = false }: { count?: number; avatar?: boolean }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonRow key={i} avatar={avatar} />
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
  row: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    padding: 10,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.sm,
  },
  rowThumb: { width: 64, height: 64, borderRadius: Radius.sm },
  rowAvatar: { width: 40, height: 40, borderRadius: Radius.full },
  rowBody: { flex: 1, gap: 8 },
  rowTitle: { width: '55%', height: 15, borderRadius: 4 },
  rowMeta: { width: '35%', height: 11, borderRadius: 4 },
});
