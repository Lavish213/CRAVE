// src/components/Toast.tsx
import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text } from 'react-native';
import * as Haptics from 'expo-haptics';
import { useToast } from '../hooks/useToast';
import { Colors, Shadows } from '../constants/colors';

export function ToastContainer() {
  const message = useToast((s) => s.message);
  const opacity = useRef(new Animated.Value(0)).current;
  const prevMessage = useRef<string | null>(null);
  const isVisible = useRef(false);

  useEffect(() => {
    if (message && message !== prevMessage.current) {
      prevMessage.current = message;
      isVisible.current = true;
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      Animated.timing(opacity, { toValue: 1, duration: 180, useNativeDriver: true }).start();
    }
    if (!message) {
      Animated.timing(opacity, { toValue: 0, duration: 220, useNativeDriver: true }).start(() => {
        prevMessage.current = null;
        isVisible.current = false;
      });
    }
  }, [message]);

  if (!message && !isVisible.current) return null;

  return (
    <Animated.View style={[styles.container, { opacity }]} pointerEvents="none">
      <Text style={styles.text}>{message}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 96,
    left: 24,
    right: 24,
    backgroundColor: Colors.border + 'EE', // Colors.border is '#2A2A2A' — same color, translucent
    borderRadius: 12,
    paddingHorizontal: 18,
    paddingVertical: 13,
    alignItems: 'center',
    ...Shadows.floating,
    zIndex: 9999,
  },
  text: { color: Colors.text, fontSize: 14, fontWeight: '600', textAlign: 'center' },
});
