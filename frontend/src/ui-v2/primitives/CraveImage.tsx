import React, { useState } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Image, type ImageProps } from 'expo-image';
import { uiColors, uiRadius } from '../tokens';
import { CraveText } from './CraveText';

export type CraveImageState = 'available' | 'missing' | 'failed';

export interface CraveImageProps extends Omit<ImageProps, 'source' | 'style'> {
  source?: ImageProps['source'] | null;
  style?: ImageProps['style'];
  accessibilityLabel?: string;
  fallbackLabel?: string;
  onStateChange?: (state: CraveImageState) => void;
}

export function CraveImage({
  source,
  style,
  accessibilityLabel,
  fallbackLabel = 'Photo unavailable',
  onStateChange,
  onError,
  onLoad,
  ...props
}: CraveImageProps) {
  const [failed, setFailed] = useState(false);
  const state: CraveImageState = !source ? 'missing' : failed ? 'failed' : 'available';

  if (state !== 'available') {
    return (
      <View
        style={[styles.fallback, style as StyleProp<ViewStyle>]}
        accessible
        accessibilityRole="image"
        accessibilityLabel={accessibilityLabel ?? fallbackLabel}
      >
        <CraveText role="caption" tone="secondary" align="center">
          {fallbackLabel}
        </CraveText>
      </View>
    );
  }

  return (
    <Image
      {...props}
      source={source}
      style={style}
      contentFit={props.contentFit ?? 'cover'}
      cachePolicy={props.cachePolicy ?? 'memory-disk'}
      accessibilityLabel={accessibilityLabel}
      onError={(event) => {
        setFailed(true);
        onStateChange?.('failed');
        onError?.(event);
      }}
      onLoad={(event) => {
        onStateChange?.('available');
        onLoad?.(event);
      }}
    />
  );
}

const styles = StyleSheet.create({
  fallback: {
    overflow: 'hidden',
    borderRadius: uiRadius.media,
    backgroundColor: uiColors.surface.elevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
