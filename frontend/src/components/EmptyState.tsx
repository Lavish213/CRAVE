// src/components/EmptyState.tsx
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../constants/colors';

interface Props {
  icon?: keyof typeof Ionicons.glyphMap;
  title: string;
  body?: string;
  ctaLabel?: string;
  onCta?: () => void;
}

export function EmptyState({ icon = 'search-outline', title, body, ctaLabel, onCta }: Props) {
  return (
    <View style={styles.container}>
      <Ionicons name={icon} size={44} color={Colors.textSecondary} />
      <Text style={styles.title}>{title}</Text>
      {body ? <Text style={styles.body}>{body}</Text> : null}
      {ctaLabel && onCta ? (
        <TouchableOpacity style={styles.cta} onPress={onCta} activeOpacity={0.75} accessibilityRole="button" accessibilityLabel={ctaLabel}>
          <Text style={styles.ctaText}>{ctaLabel}</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    paddingHorizontal: 32,
    paddingTop: 60,
    // Explicit background, not left to whatever wraps this component:
    // React Navigation's bottom-tabs paint an opaque near-white default
    // (colors.background from its own DefaultTheme) behind every screen
    // unless something paints over it first. Callers that return
    // <EmptyState /> as their entire screen content (e.g. a signed-out
    // gate) previously had no other element to do that painting, so
    // this white-text-on-title (Colors.text, #FFFFFF) rendered directly
    // over that near-white default -- illegible. Painting it here makes
    // every EmptyState usage safe regardless of what wraps it.
    backgroundColor: Colors.background,
  },
  title: { color: Colors.text, fontSize: 18, fontWeight: '700', textAlign: 'center' },
  body: { color: Colors.textSecondary, fontSize: 14, textAlign: 'center', lineHeight: 20 },
  cta: {
    marginTop: 6,
    paddingHorizontal: 22,
    paddingVertical: 11,
    borderRadius: 22,
    backgroundColor: Colors.primary,
    minHeight: 44,
    justifyContent: 'center',
  },
  ctaText: { color: '#FFFFFF', fontSize: 14, fontWeight: '700' },
});
