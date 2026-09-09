import React from 'react';
import { StyleSheet, View } from 'react-native';
import { uiColors, uiRadius, uiSpace } from '../tokens';
import { CraveText } from '../primitives';

export interface PlaceIdentityFallbackProps {
  name: string;
  category?: string | null;
  compact?: boolean;
}

export function PlaceIdentityFallback({ name, category, compact = false }: PlaceIdentityFallbackProps) {
  const initial = (name.trim()[0] || '?').toUpperCase();

  return (
    <View style={[styles.container, compact ? styles.compact : styles.regular]} accessible accessibilityLabel={`${name}, photo unavailable`}>
      <View style={[styles.initial, compact ? styles.initialCompact : styles.initialRegular]}>
        <CraveText role={compact ? 'subtitle' : 'headline'} tone="secondary">{initial}</CraveText>
      </View>
      {!compact ? (
        <View style={styles.copy}>
          <CraveText role="title" numberOfLines={3}>{name}</CraveText>
          {category ? <CraveText role="body" tone="secondary">{category}</CraveText> : null}
          <CraveText role="caption" tone="secondary">Photo unavailable</CraveText>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: uiColors.surface.elevated,
    borderRadius: uiRadius.media,
    overflow: 'hidden',
  },
  regular: {
    minHeight: 176,
    padding: uiSpace.lg,
    justifyContent: 'flex-end',
    gap: uiSpace.md,
  },
  compact: {
    width: 72,
    height: 72,
    alignItems: 'center',
    justifyContent: 'center',
  },
  initial: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: uiColors.surface.primary,
    borderRadius: uiRadius.pill,
  },
  initialCompact: {
    width: 44,
    height: 44,
  },
  initialRegular: {
    width: 56,
    height: 56,
  },
  copy: {
    gap: uiSpace.xs,
  },
});
