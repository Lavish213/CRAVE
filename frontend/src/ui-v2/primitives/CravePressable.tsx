import React from 'react';
import { Pressable, StyleSheet, type PressableProps, type StyleProp, type ViewStyle } from 'react-native';
import { uiControl } from '../tokens';

export interface CravePressableProps extends Omit<PressableProps, 'style'> {
  style?: StyleProp<ViewStyle>;
  compactTarget?: boolean;
}

export function CravePressable({ style, disabled, compactTarget = false, ...props }: CravePressableProps) {
  return (
    <Pressable
      {...props}
      disabled={disabled}
      accessibilityRole={props.accessibilityRole ?? 'button'}
      accessibilityState={{ ...props.accessibilityState, disabled: Boolean(disabled) }}
      style={({ pressed }) => [
        styles.base,
        style,
        !compactTarget && styles.minimumTarget,
        pressed && !disabled ? styles.pressed : null,
        disabled ? styles.disabled : null,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  base: {
    justifyContent: 'center',
  },
  minimumTarget: {
    minWidth: uiControl.minTarget,
    minHeight: uiControl.minTarget,
  },
  pressed: {
    opacity: uiControl.pressedOpacity,
  },
  disabled: {
    opacity: uiControl.disabledOpacity,
  },
});
