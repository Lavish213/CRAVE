// src/components/MapBottomSheet.tsx
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../constants/colors';
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
  if (!feature) return null;

  const tierKey: TierKey = TIER_MAP[feature.tier] ?? 'new';
  const tier = TIERS[tierKey];

  return (
    <View style={styles.sheet}>
      <TouchableOpacity
        style={styles.closeBtn}
        onPress={onClose}
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
    </View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: Colors.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 16,
    paddingBottom: 32,
    borderTopWidth: 1,
    borderColor: Colors.border,
    shadowColor: '#000',
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: -4 },
    elevation: 16,
  },
  closeBtn: {
    position: 'absolute',
    top: 12,
    right: 16,
    padding: 6,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 8 },
  thumb: { width: 60, height: 60, borderRadius: 10 },
  thumbFallback: {
    backgroundColor: Colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  meta: { flex: 1, gap: 4 },
  name: { color: Colors.text, fontSize: 16, fontWeight: '700' },
  category: { color: Colors.textSecondary, fontSize: 13 },
});
