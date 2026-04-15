// src/components/TrustLine.tsx
import React from 'react';
import { StyleSheet, Text, TextStyle } from 'react-native';

interface Props {
  text: string;
  color: string;
  style?: TextStyle;
  numberOfLines?: number;
}

export function TrustLine({ text, color, style, numberOfLines = 1 }: Props) {
  return (
    <Text
      style={[styles.text, { color }, style]}
      numberOfLines={numberOfLines}
    >
      {text}
    </Text>
  );
}

const styles = StyleSheet.create({
  text: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
});
