import React, { forwardRef } from 'react';
import { StyleSheet, TextInput, type TextInputProps } from 'react-native';
import { uiColors, uiControl, uiRadius, uiSpace, uiType } from '../tokens';

export interface CraveInputProps extends TextInputProps {
  invalid?: boolean;
  selected?: boolean;
}

export const CraveInput = forwardRef<TextInput, CraveInputProps>(function CraveInput(
  { invalid = false, selected = false, style, editable = true, ...props },
  ref,
) {
  const borderColor = invalid
    ? uiColors.border.destructive
    : selected
      ? uiColors.border.selected
      : uiColors.border.subtle;

  return (
    <TextInput
      ref={ref}
      {...props}
      editable={editable}
      allowFontScaling
      placeholderTextColor={props.placeholderTextColor ?? uiColors.text.secondary}
      selectionColor={uiColors.accent.selected}
      style={[
        styles.input,
        { borderColor, opacity: editable ? 1 : uiControl.disabledOpacity },
        style,
      ]}
    />
  );
});

const styles = StyleSheet.create({
  input: {
    minHeight: uiControl.minTarget,
    backgroundColor: uiColors.surface.primary,
    borderWidth: 1,
    borderRadius: uiRadius.control,
    paddingHorizontal: uiSpace.controlInset,
    paddingVertical: uiSpace.sm,
    color: uiColors.text.primary,
    ...uiType.body,
  },
});
