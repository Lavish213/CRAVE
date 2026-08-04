// src/components/ReportPhotoSheet.tsx
//
// The user-facing half of moderation. Automated screening catches what it
// can measure — unsafe, blurry, duplicate — but it cannot tell that a
// sharp, well-lit, perfectly safe photo is of the wrong restaurant. Only a
// person looking at it can, so there has to be somewhere for them to say so.
//
// Reporting is intentionally low-ceremony (pick a reason, done) and always
// reports success back, including when the server says "already_reported".
// Telling someone their report didn't count invites them to spam it.
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

import { Colors, Radius, Spacing } from '../constants/colors';
import { REPORT_REASONS, ReportReason, reportImage } from '../api/social';

interface Props {
  visible: boolean;
  imageId: string | null;
  onClose: () => void;
  onReported?: () => void;
}

export function ReportPhotoSheet({ visible, imageId, onClose, onReported }: Props) {
  const [submitting, setSubmitting] = useState<ReportReason | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handlePick = async (reason: ReportReason) => {
    if (!imageId || submitting) return;
    setSubmitting(reason);
    setError(null);
    try {
      await reportImage(imageId, reason);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      onReported?.();
      onClose();
    } catch (err: any) {
      setError(
        err?.response?.status === 401
          ? 'Sign in to report a photo.'
          : "Couldn't send that report. Try again.",
      );
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="Dismiss" />
      <View style={styles.sheet}>
        <View style={styles.grabber} />

        <Text style={styles.title}>Report this photo</Text>
        <Text style={styles.subtitle}>
          Thanks — reports are reviewed, and photos flagged by several people
          are hidden while we look.
        </Text>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <View style={styles.list}>
          {REPORT_REASONS.map((option) => (
            <TouchableOpacity
              key={option.value}
              style={styles.row}
              onPress={() => handlePick(option.value)}
              disabled={submitting !== null}
              activeOpacity={0.75}
              accessibilityRole="button"
              accessibilityLabel={option.label}
            >
              <Text style={styles.rowText}>{option.label}</Text>
              {submitting === option.value ? (
                <ActivityIndicator size="small" color={Colors.primary} />
              ) : (
                <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} />
              )}
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity
          style={styles.cancel}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel="Cancel"
        >
          <Text style={styles.cancelText}>Cancel</Text>
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)' },
  sheet: {
    backgroundColor: Colors.surface,
    borderTopLeftRadius: Radius.pill,
    borderTopRightRadius: Radius.pill,
    padding: Spacing.lg,
    paddingBottom: Spacing.xxl,
    borderTopWidth: 1,
    borderColor: Colors.border,
    gap: Spacing.sm,
  },
  grabber: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: Colors.border,
    marginBottom: Spacing.sm,
  },
  title: { color: Colors.text, fontSize: 19, fontWeight: '800' },
  subtitle: { color: Colors.textSecondary, fontSize: 13, lineHeight: 18 },
  error: { color: Colors.error, fontSize: 13 },
  list: { marginTop: Spacing.sm, gap: Spacing.xs },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: Spacing.md,
    backgroundColor: Colors.surfaceElevated,
    borderRadius: Radius.md,
    minHeight: 48,
  },
  rowText: { color: Colors.text, fontSize: 15, fontWeight: '600' },
  cancel: {
    marginTop: Spacing.sm,
    paddingVertical: 14,
    alignItems: 'center',
    minHeight: 48,
    justifyContent: 'center',
  },
  cancelText: { color: Colors.textSecondary, fontSize: 15, fontWeight: '700' },
});
