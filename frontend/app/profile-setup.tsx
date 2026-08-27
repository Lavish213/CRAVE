// app/profile-setup.tsx
//
// One-time username claim. Everything social keys off the handle, so this
// gates the profile tab rather than being an optional nicety.
//
// Availability is checked as you type (debounced) instead of only on
// submit — finding out your handle is taken after committing to it is the
// single most avoidable friction point in a signup flow.
import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';

import { Colors, Radius, Spacing } from '../src/constants/colors';
import { checkUsernameAvailable, setupProfile } from '../src/api/social';

const USERNAME_RULES = /^[a-z0-9_]{3,20}$/;
const DEBOUNCE_MS = 400;

type Availability = 'idle' | 'checking' | 'available' | 'taken' | 'invalid';

export default function ProfileSetupScreen() {
  const router = useRouter();

  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [availability, setAvailability] = useState<Availability>('idle');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Guards against an earlier, slower check resolving after a later one
  // and overwriting the newer answer.
  const latestQuery = useRef('');

  useEffect(() => {
    const normalized = username.trim().toLowerCase();
    latestQuery.current = normalized;

    if (timer.current) clearTimeout(timer.current);

    if (!normalized) {
      setAvailability('idle');
      return;
    }
    if (!USERNAME_RULES.test(normalized)) {
      setAvailability('invalid');
      return;
    }

    setAvailability('checking');
    timer.current = setTimeout(() => {
      checkUsernameAvailable(normalized)
        .then((ok) => {
          if (latestQuery.current !== normalized) return;
          setAvailability(ok ? 'available' : 'taken');
        })
        .catch(() => {
          if (latestQuery.current !== normalized) return;
          setAvailability('idle');
        });
    }, DEBOUNCE_MS);

    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [username]);

  const canSubmit = availability === 'available' && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await setupProfile(username.trim().toLowerCase(), displayName.trim() || undefined);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      router.replace('/profile');
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Couldn't claim that username.");
    } finally {
      setSubmitting(false);
    }
  };

  const hint = {
    idle: 'Letters, numbers and underscores. 3-20 characters.',
    invalid: 'Letters, numbers and underscores only, 3-20 characters.',
    checking: 'Checking…',
    available: 'Available',
    taken: 'Already taken',
  }[availability];

  const hintColor =
    availability === 'available'
      ? Colors.success
      : availability === 'taken' || availability === 'invalid'
        ? Colors.error
        : Colors.textSecondary;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Pick your handle</Text>
        <Text style={styles.subtitle}>
          This is how friends find you and how you show up on leaderboards.
        </Text>

        <View style={styles.field}>
          <Text style={styles.label}>Username</Text>
          <View style={styles.inputWrap}>
            <Text style={styles.at}>@</Text>
            <TextInput
              style={styles.input}
              value={username}
              onChangeText={setUsername}
              autoCapitalize="none"
              autoCorrect={false}
              autoFocus
              maxLength={20}
              placeholder="yourname"
              placeholderTextColor={Colors.textSecondary}
              accessibilityLabel="Username"
            />
            {availability === 'checking' ? (
              <ActivityIndicator size="small" color={Colors.textSecondary} />
            ) : availability === 'available' ? (
              <Ionicons name="checkmark-circle" size={20} color={Colors.success} />
            ) : availability === 'taken' || availability === 'invalid' ? (
              <Ionicons name="close-circle" size={20} color={Colors.error} />
            ) : null}
          </View>
          <Text style={[styles.hint, { color: hintColor }]}>{hint}</Text>
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>Display name (optional)</Text>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.input}
              value={displayName}
              onChangeText={setDisplayName}
              maxLength={60}
              placeholder="How your name shows up"
              placeholderTextColor={Colors.textSecondary}
              accessibilityLabel="Display name"
            />
          </View>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.cta, !canSubmit ? styles.ctaDisabled : null]}
          onPress={handleSubmit}
          disabled={!canSubmit}
          accessibilityRole="button"
          accessibilityLabel="Continue"
        >
          {submitting ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.ctaText}>Continue</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.lg, gap: Spacing.lg },
  title: { color: Colors.text, fontSize: 26, fontWeight: '800' },
  subtitle: { color: Colors.textSecondary, fontSize: 14, lineHeight: 20, marginTop: -Spacing.sm },
  field: { gap: Spacing.xs },
  label: { color: Colors.textSecondary, fontSize: 13, fontWeight: '600' },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.md,
    minHeight: 50,
  },
  at: { color: Colors.textSecondary, fontSize: 16, fontWeight: '700' },
  input: { flex: 1, color: Colors.text, fontSize: 16, paddingVertical: 12 },
  hint: { fontSize: 12, marginTop: 2 },
  error: { color: Colors.error, fontSize: 13 },
  cta: {
    backgroundColor: Colors.primary,
    borderRadius: Radius.pill,
    paddingVertical: 15,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50,
  },
  ctaDisabled: { opacity: 0.4 },
  ctaText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
});
