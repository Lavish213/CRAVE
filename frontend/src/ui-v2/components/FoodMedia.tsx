import React from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import type { ImageProps } from 'expo-image';
import { uiColors, uiMedia, uiRadius } from '../tokens';
import { CraveImage, CraveText } from '../primitives';

export type FoodMediaVariant = 'hero' | 'supporting' | 'compact';

export interface FoodMediaProps {
  source?: ImageProps['source'] | null;
  placeName: string;
  variant?: FoodMediaVariant;
  style?: StyleProp<ViewStyle>;
}

export function FoodMedia({ source, placeName, variant = 'supporting', style }: FoodMediaProps) {
  const fallback = (
    <View style={[styles.fallback, variant === 'compact' ? styles.compact : styles.flexible, style]}>
      <CraveText role={variant === 'hero' ? 'title' : 'caption'} tone="secondary" align="center">
        {placeName}
      </CraveText>
      <CraveText role="caption" tone="secondary" align="center">
        Photo unavailable
      </CraveText>
    </View>
  );

  if (!source) return fallback;

  return (
    <CraveImage
      source={source}
      accessibilityLabel={`Food or restaurant photo for ${placeName}`}
      fallbackLabel="Photo unavailable"
      style={[
        styles.media,
        variant === 'hero' ? styles.hero : null,
        variant === 'supporting' ? styles.supporting : null,
        variant === 'compact' ? styles.compact : null,
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  media: {
    width: '100%',
    overflow: 'hidden',
    borderRadius: uiRadius.media,
  },
  hero: {
    aspectRatio: uiMedia.heroAspectRatio,
  },
  supporting: {
    aspectRatio: uiMedia.supportingAspectRatio,
  },
  compact: {
    width: uiMedia.compactSize,
    height: uiMedia.compactSize,
  },
  flexible: {
    width: '100%',
    minHeight: 112,
  },
  fallback: {
    backgroundColor: uiColors.surface.elevated,
    borderRadius: uiRadius.media,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    gap: 4,
  },
});
