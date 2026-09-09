import React from 'react';
import { StyleSheet, View, type ViewProps } from 'react-native';
import { uiColors, uiRadius } from '../tokens';

export interface CraveSkeletonProps extends ViewProps {
  rounded?: boolean;
}

/** Static by default so loading never depends on animation for meaning. */
export function CraveSkeleton({ rounded = false, style, ...props }: CraveSkeletonProps) {
  return <View {...props} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={[styles.base, rounded ? styles.rounded : null, style]} />;
}

const styles = StyleSheet.create({
  base: {
    backgroundColor: uiColors.surface.elevated,
    borderRadius: uiRadius.control,
  },
  rounded: {
    borderRadius: uiRadius.pill,
  },
});
