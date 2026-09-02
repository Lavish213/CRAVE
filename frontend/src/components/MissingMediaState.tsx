// src/components/MissingMediaState.tsx
//
// Shared "no photo" state for anywhere a place's hero/card image would
// normally go -- PlaceCard's full-bleed card image and ImageGallery's
// Place Detail hero. Both previously filled the exact same vertical
// space a real photo would (220px / 280px) with a fallback panel, which
// reads as a stretched/broken image rather than an honest "no photo
// yet" signal and wastes most of the card/hero on nothing. This is
// deliberately compact (`height` is passed in per caller, expected to
// be materially smaller than the real-photo height) and says plainly
// that no photo exists, rather than filling the space with a decorative
// initial letter that could be mistaken for a stylistic choice.
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing } from '../constants/colors';

interface Props {
  height: number;
  accessibilityLabel: string;
}

export function MissingMediaState({ height, accessibilityLabel }: Props) {
  return (
    <View
      style={[styles.container, { height }]}
      accessible
      accessibilityLabel={accessibilityLabel}
    >
      <Ionicons name="camera-outline" size={24} color={Colors.textSecondary} />
      <Text style={styles.text}>No photo yet</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    backgroundColor: Colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.xs,
  },
  text: {
    fontSize: 12,
    color: Colors.textSecondary,
    fontWeight: '500',
  },
});
