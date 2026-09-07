import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';

import { Colors, Radius, Spacing, Typography } from '../constants/colors';
import type { RankQueueItem } from '../api/rankHome';

interface Props {
  item: RankQueueItem;
  onPress: () => void;
}

function relativeVisitLabel(value: string): string {
  const parsed = new Date(value).getTime();
  if (!Number.isFinite(parsed)) return 'Visited';
  const days = Math.max(0, Math.floor((Date.now() - parsed) / 86_400_000));
  if (days === 0) return 'Visited today';
  if (days === 1) return 'Visited yesterday';
  if (days < 7) return `Visited ${days} days ago`;
  if (days < 30) return `Visited ${Math.floor(days / 7)}w ago`;
  return 'Visited a while ago';
}

function RankQueueRowImpl({ item, onPress }: Props) {
  return (
    <TouchableOpacity
      style={styles.row}
      onPress={onPress}
      activeOpacity={0.75}
      accessibilityRole="button"
      accessibilityLabel={`Rank ${item.name}. ${relativeVisitLabel(item.visited_at)}.`}
    >
      {item.primary_image_url ? (
        <Image
          source={item.primary_image_url}
          style={styles.thumb}
          contentFit="cover"
          transition={120}
          cachePolicy="memory-disk"
        />
      ) : (
        <View style={[styles.thumb, styles.fallback]}>
          <Ionicons name="restaurant-outline" size={18} color={Colors.textSecondary} />
        </View>
      )}

      <View style={styles.meta}>
        <Text style={styles.name} numberOfLines={1}>{item.name}</Text>
        <Text style={styles.visit}>{relativeVisitLabel(item.visited_at)}</Text>
      </View>

      <View style={styles.action}>
        <Text style={styles.actionText}>Rank</Text>
        <Ionicons name="chevron-forward" size={16} color={Colors.primary} />
      </View>
    </TouchableOpacity>
  );
}

export const RankQueueRow = React.memo(RankQueueRowImpl);

const styles = StyleSheet.create({
  row: {
    minHeight: 72,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    backgroundColor: Colors.surface,
  },
  thumb: { width: 48, height: 48, borderRadius: Radius.sm },
  fallback: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.surfaceElevated,
  },
  meta: { flex: 1, gap: Spacing.xs },
  name: { ...Typography.label, color: Colors.text },
  visit: { ...Typography.caption, color: Colors.textSecondary },
  action: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xs },
  actionText: { ...Typography.caption, color: Colors.primary, fontWeight: '700' },
});
