import React from 'react';
import { StyleSheet, View } from 'react-native';
import { uiColors, uiRadius } from '../tokens';
import { CravePressable, type CravePressableProps } from './CravePressable';

export interface CraveIconButtonProps extends Omit<CravePressableProps, 'children' | 'accessibilityLabel'> {
  accessibilityLabel: string;
  icon: React.ReactNode;
  selected?: boolean;
}

export function CraveIconButton({ accessibilityLabel, icon, selected = false, style, ...props }: CraveIconButtonProps) {
  return (
    <CravePressable
      {...props}
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ ...props.accessibilityState, selected }}
      style={[
        styles.button,
        selected ? styles.selected : null,
        style,
      ]}
    >
      <View pointerEvents="none">{icon}</View>
    </CravePressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: uiRadius.control,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  selected: {
    backgroundColor: uiColors.surface.selected,
    borderColor: uiColors.border.selected,
  },
});
