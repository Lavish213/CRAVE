import React from 'react';
import { StyleSheet, View, type ViewProps } from 'react-native';
import { uiColors, uiElevation, uiRadius, uiSpace } from '../tokens';

/**
 * Visual sheet surface only. This primitive deliberately does not own modal,
 * gesture, drag, or navigation mechanics; existing flow owners such as
 * MapBottomSheet keep those behaviors and compose this surface.
 */
export function CraveSheet({ style, ...props }: ViewProps) {
  return <View {...props} style={[styles.sheet, style]} />;
}

const styles = StyleSheet.create({
  sheet: {
    backgroundColor: uiColors.surface.overlay,
    borderTopLeftRadius: uiRadius.sheet,
    borderTopRightRadius: uiRadius.sheet,
    borderWidth: 1,
    borderBottomWidth: 0,
    borderColor: uiColors.border.subtle,
    padding: uiSpace.lg,
    ...uiElevation.sheet,
  },
});
