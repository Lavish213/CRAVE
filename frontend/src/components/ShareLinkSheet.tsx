// src/components/ShareLinkSheet.tsx
//
// The actual entry point into the share-to-CRAVE pipeline. Until this
// existed, POST /api/v1/share was a fully working backend endpoint with
// zero frontend caller anywhere in the app — nothing let a user submit a
// TikTok/IG/YouTube link at all. This is a manual paste-the-link flow
// rather than the OS native share sheet (registering CRAVE as a share
// target requires expo-share-intent + a native rebuild off Expo Go — a
// separate, bigger infra step). This ships the pipeline a real front door
// today without that dependency.
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { Colors, Spacing, Radius } from '../constants/colors';
import { detectSourceType, submitPlaceSave, submitShare } from '../api/crave';
import { useLocation } from '../hooks/useLocation';

interface Props {
  visible: boolean;
  onClose: () => void;
  onSubmitted?: () => void;
}

type Mode = 'link' | 'name';

const PLATFORM_LABEL: Record<string, string> = {
  tiktok: 'TikTok',
  instagram: 'Instagram',
  youtube: 'YouTube',
  twitter: 'X / Twitter',
  web: 'Web link',
  other: 'Link',
};

export function ShareLinkSheet({ visible, onClose, onSubmitted }: Props) {
  const [mode, setMode] = useState<Mode>('link');
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Cached/shared location hook — no fresh GPS prompt, just attaches
  // whatever CRAVE already has on hand to raise the candidate's confidence
  // a bit. Never blocks submission if unavailable.
  const location = useLocation();

  const trimmed = url.trim();
  const trimmedName = name.trim();
  const detected = trimmed.length > 10 ? detectSourceType(trimmed) : null;

  const reset = () => {
    setUrl('');
    setName('');
    setError(null);
  };

  const handleClose = () => {
    if (submitting) return;
    reset();
    setMode('link');
    onClose();
  };

  const handleSubmitLink = async () => {
    if (trimmed.length < 10) {
      setError('Paste a link to a restaurant video or post');
      return;
    }
    if (!/^https?:\/\//i.test(trimmed)) {
      setError('Needs to start with http:// or https://');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      await submitShare(trimmed);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      reset();
      onSubmitted?.();
      onClose();
    } catch (err: any) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      const status = err?.response?.status;
      if (status === 401) {
        setError('Sign in to share a link');
      } else if (status === 429) {
        setError("You're doing that too fast — wait a moment and try again.");
      } else {
        setError("Couldn't submit that link. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitName = async () => {
    if (trimmedName.length < 2) {
      setError('Enter the name of the place');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      await submitPlaceSave(trimmedName, { lat: location?.lat, lng: location?.lng });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      reset();
      onSubmitted?.();
      onClose();
    } catch (err: any) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      const status = err?.response?.status;
      if (status === 401) {
        setError('Sign in to add a place');
      } else if (status === 429) {
        setError("You're doing that too fast — wait a moment and try again.");
      } else {
        setError("Couldn't submit that. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={handleClose}
      statusBarTranslucent
    >
      <Pressable style={styles.backdrop} onPress={handleClose} />

      <View style={styles.sheet}>
        <View style={styles.handle} />

        <TouchableOpacity
          style={styles.closeBtn}
          onPress={handleClose}
          accessibilityRole="button"
          accessibilityLabel="Close"
        >
          <Ionicons name="close" size={20} color={Colors.textSecondary} />
        </TouchableOpacity>

        <View style={styles.identity}>
          <Text style={styles.title}>{mode === 'link' ? 'Share a link' : 'Add a place'}</Text>
          <Text style={styles.body}>
            {mode === 'link'
              ? "Paste a TikTok, Instagram, YouTube, or article link about a restaurant. We'll match it to the place automatically."
              : "No link? Just tell us the name — we'll do the rest."}
          </Text>
        </View>

        <View style={styles.modeToggle}>
          <TouchableOpacity
            style={[styles.modeBtn, mode === 'link' && styles.modeBtnActive]}
            onPress={() => {
              setMode('link');
              setError(null);
            }}
            accessibilityRole="button"
            accessibilityLabel="Switch to link mode"
          >
            <Text style={[styles.modeBtnText, mode === 'link' && styles.modeBtnTextActive]}>Link</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.modeBtn, mode === 'name' && styles.modeBtnActive]}
            onPress={() => {
              setMode('name');
              setError(null);
            }}
            accessibilityRole="button"
            accessibilityLabel="Switch to just-the-name mode"
          >
            <Text style={[styles.modeBtnText, mode === 'name' && styles.modeBtnTextActive]}>Just the name</Text>
          </TouchableOpacity>
        </View>

        {mode === 'link' ? (
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.input}
              placeholder="https://..."
              placeholderTextColor={Colors.textSecondary}
              value={url}
              onChangeText={(v) => {
                setUrl(v);
                if (error) setError(null);
              }}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              editable={!submitting}
              accessibilityLabel="Link URL"
            />
            {detected ? (
              <View style={styles.platformChip}>
                <Text style={styles.platformChipText}>{PLATFORM_LABEL[detected]}</Text>
              </View>
            ) : null}
          </View>
        ) : (
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.input}
              placeholder="Restaurant name"
              placeholderTextColor={Colors.textSecondary}
              value={name}
              onChangeText={(v) => {
                setName(v);
                if (error) setError(null);
              }}
              autoCapitalize="words"
              editable={!submitting}
              accessibilityLabel="Place name"
            />
          </View>
        )}

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.submitBtn, submitting && styles.submitBtnDisabled]}
          onPress={mode === 'link' ? handleSubmitLink : handleSubmitName}
          disabled={submitting}
          activeOpacity={0.85}
          accessibilityRole="button"
          accessibilityLabel="Submit"
        >
          {submitting ? (
            <ActivityIndicator color={Colors.background} size="small" />
          ) : (
            <Text style={styles.submitBtnText}>Submit</Text>
          )}
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.65)' },
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
  title: { fontSize: 22, fontWeight: '800', color: Colors.text, marginBottom: Spacing.sm },
  body: { fontSize: 14, color: Colors.textSecondary, lineHeight: 20 },
  modeToggle: {
    flexDirection: 'row',
    marginHorizontal: Spacing.xl,
    marginBottom: Spacing.md,
    backgroundColor: Colors.surfaceElevated,
    borderRadius: Radius.pill,
    padding: 3,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modeBtn: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: Radius.pill,
  },
  modeBtnActive: { backgroundColor: Colors.primary },
  modeBtnText: { fontSize: 13, fontWeight: '700', color: Colors.textSecondary },
  modeBtnTextActive: { color: Colors.background },
  inputWrap: { paddingHorizontal: Spacing.xl, gap: Spacing.sm },
  input: {
    height: 52,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surfaceElevated,
    paddingHorizontal: Spacing.md,
    color: Colors.text,
    fontSize: 15,
  },
  platformChip: {
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: Radius.pill,
    backgroundColor: Colors.primary + '22',
  },
  platformChipText: { fontSize: 12, fontWeight: '700', color: Colors.primary },
  error: {
    color: Colors.error,
    fontSize: 13,
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.sm,
  },
  submitBtn: {
    marginTop: Spacing.lg,
    marginHorizontal: Spacing.xl,
    height: 52,
    borderRadius: Radius.md,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  submitBtnDisabled: { opacity: 0.6 },
  submitBtnText: { fontSize: 16, fontWeight: '700', color: Colors.background },
});
