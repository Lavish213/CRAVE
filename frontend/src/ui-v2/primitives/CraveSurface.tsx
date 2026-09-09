import React from 'react';
import { StyleSheet, View, type ViewProps } from 'react-native';
import { uiColors, uiElevation, uiRadius, type UiSurfaceTone } from '../tokens';

type ElevationRole = keyof typeof uiElevation;
type RadiusRole = keyof typeof uiRadius | 'none';

export interface CraveSurfaceProps extends ViewProps {
  tone?: UiSurfaceTone;
  elevation?: ElevationRole | 'none';
  radius?: RadiusRole;
}

const surfaceColors: Record<UiSurfaceTone, string> = {
  canvas: uiColors.surface.canvas,
  primary: uiColors.surface.primary,
  elevated: uiColors.surface.elevated,
  overlay: uiColors.surface.overlay,
  selected: uiColors.surface.selected,
};

export function CraveSurface({ tone = 'primary', elevation = 'none', radius = 'none', style, ...props }: CraveSurfaceProps) {
  return (
    <View
      {...props}
      style={[
        styles.base,
        { backgroundColor: surfaceColors[tone] },
        radius === 'none' ? null : { borderRadius: uiRadius[radius] },
        elevation === 'none' ? null : uiElevation[elevation],
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  base: {
    position: 'relative',
  },
});
