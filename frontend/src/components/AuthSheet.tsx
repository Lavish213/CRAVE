import React, { useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { supabase } from '../lib/supabase';
import { Colors, Spacing, Radius } from '../constants/colors';

interface Props {
  visible: boolean;
  onClose: () => void;
  reason?: 'save' | 'hitlist' | 'default';
}

const REASON_COPY: Record<NonNullable<Props['reason']>, { title: string; body: string }> = {
  save: {
    title: 'Save this spot',
    body: 'Create a free account to keep your Hitlist across devices.',
  },
  hitlist: {
    title: 'Your Hitlist awaits',
    body: 'Sign in to access your saved places and food memories.',
  },
  default: {
    title: 'Join CRAVE',
    body: 'Your cultural discovery engine. Save spots, track craves, find the city.',
  },
};

export function AuthSheet({ visible, onClose, reason = 'default' }: Props) {
  const [loading, setLoading] = useState<'google' | 'apple' | null>(null);
  const copy = REASON_COPY[reason];

  const handleGoogle = async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setLoading('google');
    try {
      await supabase.auth.signInWithOAuth({ provider: 'google' });
    } finally {
      setLoading(null);
    }
  };

  const handleApple = async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setLoading('apple');
    try {
      await supabase.auth.signInWithOAuth({ provider: 'apple' });
    } finally {
      setLoading(null);
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <Pressable style={styles.backdrop} onPress={onClose} />

      <View style={styles.sheet}>
        {/* Handle */}
        <View style={styles.handle} />

        {/* Close */}
        <TouchableOpacity
          style={styles.closeBtn}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel="Close"
        >
          <Ionicons name="close" size={20} color={Colors.textSecondary} />
        </TouchableOpacity>

        {/* Identity */}
        <View style={styles.identity}>
          <Text style={styles.wordmark}>CRAVE</Text>
          <Text style={styles.title}>{copy.title}</Text>
          <Text style={styles.body}>{copy.body}</Text>
        </View>

        {/* Auth buttons */}
        <View style={styles.buttons}>
          {/* Apple */}
          <TouchableOpacity
            style={[styles.authBtn, styles.authBtnApple]}
            onPress={handleApple}
            activeOpacity={0.85}
            disabled={loading !== null}
            accessibilityRole="button"
            accessibilityLabel="Continue with Apple"
          >
            {loading === 'apple' ? (
              <ActivityIndicator color={Colors.background} size="small" />
            ) : (
              <>
                <Ionicons name="logo-apple" size={18} color={Colors.background} />
                <Text style={[styles.authBtnText, styles.authBtnTextApple]}>
                  Continue with Apple
                </Text>
              </>
            )}
          </TouchableOpacity>

          {/* Google */}
          <TouchableOpacity
            style={[styles.authBtn, styles.authBtnGoogle]}
            onPress={handleGoogle}
            activeOpacity={0.85}
            disabled={loading !== null}
            accessibilityRole="button"
            accessibilityLabel="Continue with Google"
          >
            {loading === 'google' ? (
              <ActivityIndicator color={Colors.text} size="small" />
            ) : (
              <>
                <Ionicons name="logo-google" size={16} color={Colors.text} />
                <Text style={styles.authBtnText}>Continue with Google</Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        <Text style={styles.legal}>
          By continuing you agree to our{' '}
          <Text style={styles.legalLink}>Terms</Text>
          {' & '}
          <Text style={styles.legalLink}>Privacy Policy</Text>
        </Text>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.65)',
  },
  sheet: {
    backgroundColor: Colors.surface,
    borderTopLeftRadius: Radius.card,
    borderTopRightRadius: Radius.card,
    borderTopWidth: 1,
    borderColor: Colors.border,
    paddingBottom: 40,
  },
  handle: {
    width: 36,
    height: 4,
    borderRadius: Radius.full,
    backgroundColor: Colors.border,
    alignSelf: 'center',
    marginTop: Spacing.sm,
  },
  closeBtn: {
    position: 'absolute',
    top: Spacing.sm,
    right: Spacing.md,
    padding: Spacing.sm,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  identity: {
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.lg,
  },
  wordmark: {
    fontSize: 13,
    fontWeight: '900',
    color: Colors.primary,
    letterSpacing: 3,
    marginBottom: Spacing.md,
  },
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: Colors.text,
    marginBottom: Spacing.sm,
  },
  body: {
    fontSize: 15,
    color: Colors.textSecondary,
    lineHeight: 22,
  },
  buttons: {
    paddingHorizontal: Spacing.xl,
    gap: Spacing.sm,
  },
  authBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    height: 52,
    borderRadius: Radius.md,
  },
  authBtnApple: {
    backgroundColor: Colors.text,
  },
  authBtnGoogle: {
    backgroundColor: Colors.surfaceElevated,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  authBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: Colors.text,
  },
  authBtnTextApple: {
    color: Colors.background,
  },
  legal: {
    textAlign: 'center',
    color: Colors.textMuted,
    fontSize: 12,
    marginTop: Spacing.lg,
    paddingHorizontal: Spacing.xl,
  },
  legalLink: {
    color: Colors.textSecondary,
    textDecorationLine: 'underline',
  },
});
