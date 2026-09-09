import React from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { uiColors, uiRadius, uiSpace } from '../tokens';
import { CravePressable, type CravePressableProps } from './CravePressable';
import { CraveText } from './CraveText';

export type CraveButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive';

export interface CraveButtonProps extends Omit<CravePressableProps, 'children'> {
  label: string;
  variant?: CraveButtonVariant;
  loading?: boolean;
}

const variantStyles = {
  primary: {
    backgroundColor: uiColors.accent.primaryAction,
    borderColor: uiColors.accent.primaryAction,
    textTone: 'inverse' as const,
  },
  secondary: {
    backgroundColor: 'transparent',
    borderColor: uiColors.border.strong,
    textTone: 'primary' as const,
  },
  ghost: {
    backgroundColor: 'transparent',
    borderColor: 'transparent',
    textTone: 'primary' as const,
  },
  destructive: {
    backgroundColor: uiColors.status.destructive.background,
    borderColor: uiColors.status.destructive.border,
    textTone: 'destructive' as const,
  },
};

export function CraveButton({ label, variant = 'primary', loading = false, disabled, style, ...props }: CraveButtonProps) {
  const visual = variantStyles[variant];
  const isDisabled = Boolean(disabled || loading);

  return (
    <CravePressable
      {...props}
      disabled={isDisabled}
      accessibilityLabel={props.accessibilityLabel ?? label}
      accessibilityState={{ ...props.accessibilityState, disabled: isDisabled, busy: loading }}
      style={[
        styles.button,
        { backgroundColor: visual.backgroundColor, borderColor: visual.borderColor },
        style,
      ]}
    >
      <View style={styles.content}>
        {loading ? <ActivityIndicator color={variant === 'primary' ? uiColors.text.inverse : uiColors.text.primary} /> : null}
        <CraveText role="label" tone={visual.textTone} numberOfLines={2}>
          {label}
        </CraveText>
      </View>
    </CravePressable>
  );
}

const styles = StyleSheet.create({
  button: {
    borderWidth: 1,
    borderRadius: uiRadius.control,
    paddingHorizontal: uiSpace.lg,
    paddingVertical: uiSpace.sm,
    alignItems: 'center',
  },
  content: {
    minHeight: 28,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: uiSpace.sm,
  },
});
