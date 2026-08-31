// src/components/ErrorState.tsx
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../constants/colors';

interface Props {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({ message = "Couldn't load that.", onRetry }: Props) {
  return (
    <View style={styles.container}>
      <Ionicons name="cloud-offline-outline" size={40} color={Colors.textSecondary} />
      <Text style={styles.message}>{message}</Text>
      {onRetry && (
        <TouchableOpacity style={styles.retryBtn} onPress={onRetry} activeOpacity={0.75} accessibilityRole="button" accessibilityLabel="Try again">
          <Text style={styles.retryText}>Try again</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    paddingHorizontal: 32,
    paddingTop: 60,
    // Same fix as EmptyState.tsx: React Navigation's bottom-tabs paint an
    // opaque near-white default behind every screen unless something
    // paints over it first. Most callers here return <ErrorState /> as
    // their entire screen content on an early-return (place/[id].tsx,
    // rank/[placeId].tsx, profile.tsx, etc.) with nothing else to do that
    // painting -- without this, the screen flashes to React Navigation's
    // light default instead of the app's near-black background, and the
    // retry button's white text renders on that same light default.
    backgroundColor: Colors.background,
  },
  message: { color: Colors.textSecondary, fontSize: 15, textAlign: 'center' },
  retryBtn: {
    marginTop: 4,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.border,
    minHeight: 44,
    justifyContent: 'center',
  },
  retryText: { color: Colors.text, fontSize: 14, fontWeight: '600' },
});
