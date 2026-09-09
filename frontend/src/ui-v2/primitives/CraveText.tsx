import React from 'react';
import { StyleSheet, Text, type TextProps, type TextStyle } from 'react-native';
import { uiColors, uiType, type UiTextTone, type UiTypographyRole } from '../tokens';

export interface CraveTextProps extends Omit<TextProps, 'role'> {
  role?: UiTypographyRole;
  tone?: UiTextTone;
  align?: TextStyle['textAlign'];
}

const toneColors: Record<UiTextTone, string> = {
  primary: uiColors.text.primary,
  secondary: uiColors.text.secondary,
  inverse: uiColors.text.inverse,
  disabled: uiColors.text.disabled,
  brand: uiColors.text.brand,
  positive: uiColors.text.positive,
  uncertain: uiColors.text.uncertain,
  destructive: uiColors.text.destructive,
  protected: uiColors.text.protected,
};

export function CraveText({ role = 'body', tone = 'primary', align, style, maxFontSizeMultiplier, ...props }: CraveTextProps) {
  return (
    <Text
      {...props}
      allowFontScaling
      maxFontSizeMultiplier={maxFontSizeMultiplier ?? 2}
      style={[styles.base, uiType[role], { color: toneColors[tone], textAlign: align }, style]}
    />
  );
}

const styles = StyleSheet.create({
  base: {
    flexShrink: 1,
  },
});
