// src/components/RankedPlaceRow.tsx
//
// One row of a personal ranked list. The position number is the point of
// the whole feature — a forced-rank list has no ties, so "#3" is a real
// claim about this place relative to every other one, not a star rating
// shared with fifty others.
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius, Spacing } from '../constants/colors';
import { RankTier, formatScore, tierColor } from '../utils/rankScore';

interface Props {
  position: number;
  name: string;
  imageUrl?: string | null;
  score: number;
  tier: RankTier;
  note?: string | null;
  onPress?: () => void;
  rightAction?: React.ReactNode;
}

function RankedPlaceRowImpl({
  position,
  name,
  imageUrl,
  score,
  tier,
  note,
  onPress,
  rightAction,
}: Props) {
  const body = (
    <View style={styles.row}>
      <Text style={styles.position}>{position}</Text>

      {imageUrl ? (
        <Image
          source={imageUrl}
          style={styles.thumb}
          contentFit="cover"
          transition={120}
          placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
          cachePolicy="memory-disk"
        />
      ) : (
        <View style={[styles.thumb, styles.thumbFallback]}>
          <Ionicons name="restaurant" size={18} color={Colors.textSecondary} />
        </View>
      )}

      <View style={styles.meta}>
        <Text style={styles.name} numberOfLines={1}>
          {name}
        </Text>
        {note ? (
          <Text style={styles.note} numberOfLines={1}>
            {note}
          </Text>
        ) : null}
      </View>

      <View style={[styles.scorePill, { borderColor: tierColor(tier) }]}>
        <Text style={[styles.scoreText, { color: tierColor(tier) }]}>
          {formatScore(score)}
        </Text>
      </View>

      {rightAction}
    </View>
  );

  if (!onPress) return body;

  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.75}
      accessibilityRole="button"
      accessibilityLabel={`${name}, ranked number ${position}, scored ${formatScore(score)}`}
    >
      {body}
    </TouchableOpacity>
  );
}

// See PlaceCard.tsx's identical note -- this renders as a row in ranked
// lists and shouldn't re-render on every parent state change unrelated
// to its own props.
export const RankedPlaceRow = React.memo(RankedPlaceRowImpl);

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    padding: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  position: {
    color: Colors.textSecondary,
    fontSize: 15,
    fontWeight: '800',
    minWidth: 24,
    textAlign: 'center',
  },
  thumb: { width: 48, height: 48, borderRadius: Radius.sm },
  thumbFallback: {
    backgroundColor: Colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  meta: { flex: 1 },
  name: { color: Colors.text, fontSize: 15, fontWeight: '700' },
  note: { color: Colors.textSecondary, fontSize: 12, marginTop: 2 },
  scorePill: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: Radius.pill,
    borderWidth: 1.5,
    minWidth: 44,
    alignItems: 'center',
  },
  scoreText: { fontSize: 14, fontWeight: '800' },
});
