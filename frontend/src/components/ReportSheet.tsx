// src/components/ReportSheet.tsx
//
// Shared implementation behind ReportPlaceSheet/ReportPhotoSheet/
// ReportVideoSheet -- those three were ~90% identical (same Modal/
// Pressable/backdrop/handleClose/handlePick structure), differing only
// in the entity id prop name, the reason enum/options shown, the API
// call made on submit, and copy strings. This component takes all of
// that as a `config` object; the three named exports stay as thin
// wrappers so no other call site in the app needs to change.
//
// Reporting is intentionally low-ceremony (pick a reason, done) and
// always reports success back, including when the server says
// "already_reported". Telling someone their report didn't count invites
// them to spam it.
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

export interface ReportOption<R extends string> {
  value: R;
  label: string;
}

export interface ReportSheetConfig<R extends string> {
  /** All selectable reasons, in display order. */
  reasons: ReportOption<R>[];
  /** Sheet heading, e.g. "Report this photo". */
  title: string;
  /** Copy shown under the heading. */
  subtitle: string;
  /** Message shown when the submit call 401s. */
  signInMessage: string;
  /** Makes the actual API call for the chosen reason. */
  submit: (entityId: string, reason: R) => Promise<unknown>;
  /**
   * Whether closing the sheet (backdrop tap, Cancel, hardware back)
   * also clears a stale error so reopening doesn't show it again.
   * ReportPlaceSheet does this; ReportPhotoSheet/ReportVideoSheet
   * historically did not, so it defaults to false to keep their
   * existing behavior unchanged.
   */
  resetErrorOnClose?: boolean;
}

interface ReportSheetProps<R extends string> {
  visible: boolean;
  entityId: string | null;
  onClose: () => void;
  onReported?: () => void;
  config: ReportSheetConfig<R>;
}

export function ReportSheet<R extends string>({
  visible,
  entityId,
  onClose,
  onReported,
  config,
}: ReportSheetProps<R>) {
  const [submitting, setSubmitting] = useState<R | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handlePick = async (reason: R) => {
    if (!entityId || submitting) return;
    setSubmitting(reason);
    setError(null);
    try {
      await config.submit(entityId, reason);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      onReported?.();
      onClose();
    } catch (err: any) {
      setError(
        err?.response?.status === 401
          ? config.signInMessage
          : "Couldn't send that report. Try again.",
      );
    } finally {
      setSubmitting(null);
    }
  };

  const handleClose = () => {
    if (config.resetErrorOnClose) {
      setError(null);
    }
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={handleClose}>
      <Pressable style={styles.backdrop} onPress={handleClose} accessibilityLabel="Dismiss" />
      <View style={styles.sheet}>
        <View style={styles.grabber} />

        <Text style={styles.title}>{config.title}</Text>
        <Text style={styles.subtitle}>{config.subtitle}</Text>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <View style={styles.list}>
          {config.reasons.map((option) => (
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
                <ActivityIndicator size="small" color={Colors.brand} />
              ) : (
                <Ionicons name="chevron-forward" size={16} color={Colors.textSecondary} />
              )}
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity
          style={styles.cancel}
          onPress={handleClose}
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
  backdrop: { flex: 1, backgroundColor: Colors.sheetScrim },
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
  // These four fontSize literals are pre-existing, relocated (not
  // added) from Report{Place,Photo,Video}Sheet.tsx during the Task-1
  // dedupe; retrofitting them to a Typography role is tracked
  // follow-up debt (see PR description), not fixed here.
  // eslint-disable-next-line no-restricted-syntax
  title: { color: Colors.text, fontSize: 19, fontWeight: '800' },
  // eslint-disable-next-line no-restricted-syntax
  subtitle: { color: Colors.textSecondary, fontSize: 13, lineHeight: 18 },
  // eslint-disable-next-line no-restricted-syntax
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
  // eslint-disable-next-line no-restricted-syntax -- see `title` above.
  rowText: { color: Colors.text, fontSize: 15, fontWeight: '600' },
  cancel: {
    marginTop: Spacing.sm,
    paddingVertical: 14,
    alignItems: 'center',
    minHeight: 48,
    justifyContent: 'center',
  },
  // eslint-disable-next-line no-restricted-syntax -- see `title` above.
  cancelText: { color: Colors.textSecondary, fontSize: 15, fontWeight: '700' },
});
