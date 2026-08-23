// src/components/ShareRankCard.tsx
//
// The artifact that represents CRAVE to people who've never opened the
// app — a "just ranked" moment, not a full list export. Rendered off-
// screen and captured via react-native-view-shot from the rank "done"
// screen (see app/rank/[placeId].tsx), then handed to the native share
// sheet as an image.
//
// Voice matches the rest of the app: the score is the hero, "beat X
// head-to-head" carries the actual product mechanic (comparison-ranking,
// not a star you picked), and the footer line doubles as tagline and
// attribution — the same three moves as the rank flow's own copy.
import React, { forwardRef } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors, Radius, Spacing } from '../constants/colors';
import { RankTier, TIER_LABELS, formatScore, tierColor } from '../utils/rankScore';

export interface ShareRankCardProps {
  name: string;
  category?: string | null;
  areaName?: string | null;
  imageUrl?: string | null;
  score: number;
  tier: RankTier;
  /** Name of the place beaten in the deciding comparison, if there was one. */
  beatName?: string | null;
}

// Fixed logical size, captured at pixelRatio 3 (see the caller) — a 9:16
// "story" ratio, the share destination most of this is actually posted to.
export const SHARE_CARD_WIDTH = 320;
export const SHARE_CARD_HEIGHT = 568;

export const ShareRankCard = forwardRef<View, ShareRankCardProps>(function ShareRankCard(
  { name, category, areaName, imageUrl, score, tier, beatName },
  ref,
) {
  const accent = tierColor(tier);
  const metaLine = [category, areaName].filter(Boolean).join(' · ');

  return (
    // collapsable={false} is required on Android — otherwise the view can
    // get flattened away by the native optimizer and captureRef finds
    // nothing to snapshot.
    <View ref={ref} collapsable={false} style={styles.card}>
      {imageUrl ? (
        <Image source={imageUrl} style={StyleSheet.absoluteFill} contentFit="cover" cachePolicy="memory-disk" />
      ) : (
        <View style={[StyleSheet.absoluteFill, styles.fallback]} />
      )}
      <LinearGradient
        colors={['rgba(10,10,10,0.25)', 'rgba(10,10,10,0.55)', Colors.background]}
        locations={[0, 0.45, 1]}
        style={StyleSheet.absoluteFill}
      />

      <View style={styles.content}>
        <View style={styles.mark}>
          <View style={styles.markDot} />
          <Text style={styles.markText}>CRAVE</Text>
        </View>

        <View style={styles.main}>
          <View style={[styles.badge, { borderColor: accent, backgroundColor: accent + '22' }]}>
            <Text style={[styles.badgeText, { color: accent }]}>{TIER_LABELS[tier]}</Text>
          </View>

          <View style={styles.scoreRow}>
            <Text style={styles.score}>{formatScore(score)}</Text>
            <Text style={styles.scoreOf}>/10</Text>
          </View>

          <Text style={styles.name} numberOfLines={2}>{name}</Text>
          {metaLine ? <Text style={styles.meta}>{metaLine}</Text> : null}

          {beatName ? (
            <View style={styles.beatLine}>
              <View style={styles.beatStripe} />
              <Text style={styles.beatText}>
                Beat <Text style={styles.beatNameText}>{beatName}</Text> head-to-head. Ranked, not rated.
              </Text>
            </View>
          ) : null}
        </View>

        <View style={styles.footer}>
          <Text style={styles.tagline}>
            No stars. <Text style={styles.taglineBold}>Just rank.</Text>
          </Text>
        </View>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  card: {
    width: SHARE_CARD_WIDTH,
    height: SHARE_CARD_HEIGHT,
    backgroundColor: Colors.background,
    overflow: 'hidden',
  },
  fallback: { backgroundColor: Colors.surfaceElevated },
  content: {
    flex: 1,
    padding: Spacing.xl,
    justifyContent: 'space-between',
  },
  mark: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  markDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: Colors.primary },
  markText: { color: Colors.text, fontSize: 15, fontWeight: '800', letterSpacing: 1.2 },
  main: { gap: 4 },
  badge: {
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderRadius: Radius.pill,
    paddingHorizontal: 12,
    paddingVertical: 5,
    marginBottom: 14,
  },
  badgeText: { fontSize: 12, fontWeight: '700' },
  scoreRow: { flexDirection: 'row', alignItems: 'baseline', gap: 4 },
  score: { color: Colors.text, fontSize: 64, fontWeight: '800', lineHeight: 68 },
  scoreOf: { color: Colors.textSecondary, fontSize: 18, fontWeight: '600' },
  name: { color: Colors.text, fontSize: 22, fontWeight: '700', marginTop: 6 },
  meta: { color: Colors.textSecondary, fontSize: 14, marginTop: 3 },
  beatLine: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 20,
    padding: Spacing.md,
    borderRadius: Radius.md,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  beatStripe: { width: 3, borderRadius: 2, backgroundColor: Colors.success },
  beatText: { flex: 1, color: Colors.text, fontSize: 13, fontWeight: '600', lineHeight: 18 },
  beatNameText: { color: Colors.success },
  footer: {
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    paddingTop: Spacing.md,
  },
  tagline: { color: Colors.textSecondary, fontSize: 13, fontWeight: '600' },
  taglineBold: { color: Colors.text, fontWeight: '800' },
});
