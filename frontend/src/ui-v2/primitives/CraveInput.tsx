import React, { forwardRef } from 'react';
import { StyleSheet, TextInput, View, type StyleProp, type TextInputProps, type ViewStyle } from 'react-native';
import { uiColors, uiControl, uiRadius, uiSpace, uiType } from '../tokens';

export interface CraveInputProps extends TextInputProps {
  invalid?: boolean;
  selected?: boolean;
  leading?: React.ReactNode;
  trailing?: React.ReactNode;
  containerStyle?: StyleProp<ViewStyle>;
}

export const CraveInput = forwardRef<TextInput, CraveInputProps>(function CraveInput(
  { invalid = false, selected = false, leading, trailing, containerStyle, style, editable = true, ...props },
  ref,
) {
  const borderColor = invalid
    ? uiColors.border.destructive
    : selected
      ? uiColors.border.selected
      : uiColors.border.subtle;

  return (
    <View style={[styles.container, { borderColor, opacity: editable ? 1 : uiControl.disabledOpacity }, containerStyle]}>
      {leading ? <View pointerEvents="none" style={styles.adornment}>{leading}</View> : null}
      <TextInput
        ref={ref}
        {...props}
        editable={editable}
        allowFontScaling
        placeholderTextColor={props.placeholderTextColor ?? uiColors.text.secondary}
        selectionColor={uiColors.accent.selected}
        style={[styles.input, style]}
      />
      {trailing ? <View style={styles.adornment}>{trailing}</View> : null}
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    minHeight: uiControl.minTarget,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: uiColors.surface.primary,
    borderWidth: 1,
    borderRadius: uiRadius.control,
    paddingLeft: uiSpace.controlInset,
  },
  input: {
    flex: 1,
    minHeight: uiControl.minTarget,
    paddingHorizontal: uiSpace.sm,
    paddingVertical: uiSpace.sm,
    color: uiColors.text.primary,
    ...uiType.body,
  },
  adornment: {
    alignItems: 'center',
    justifyContent: 'center',
  },
});
