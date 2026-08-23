// src/components/MenuSubmissionSheet.tsx
//
// The user-facing entry point into menu self-submission: when a place has
// no menu on file (or the one on file is wrong/outdated), a signed-in user
// can type in a few items themselves. Nothing here is trusted directly —
// POST /places/{id}/menu/submit only ever stages a `menu_submissions` row
// pending moderator review; it never writes to the servable menu. See
// backend/app/db/models/menu_submission.py for the full pipeline.
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';

import { Colors, Spacing, Radius } from '../constants/colors';
import { submitMenu, MenuItemSubmission } from '../api/menu';

interface Props {
  visible: boolean;
  placeId: string;
  onClose: () => void;
  onSubmitted?: () => void;
}

interface DraftItem {
  key: string;
  name: string;
  category: string;
  price: string;
  description: string;
}

let _draftKeySeq = 0;
function _newDraft(): DraftItem {
  return { key: `draft-${++_draftKeySeq}`, name: '', category: '', price: '', description: '' };
}

const MAX_ITEMS = 200;

export function MenuSubmissionSheet({ visible, placeId, onClose, onSubmitted }: Props) {
  const [items, setItems] = useState<DraftItem[]>([_newDraft()]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Set alongside `error` only for the invalid-price case, which is about
  // one specific item -- lets that message render next to the offending
  // item's input instead of a generic banner the user has to go hunting
  // from. Stays null for whole-form errors (no items, sign-in, network).
  const [errorItemKey, setErrorItemKey] = useState<string | null>(null);

  const reset = () => {
    setItems([_newDraft()]);
    setError(null);
    setErrorItemKey(null);
  };

  const handleClose = () => {
    if (submitting) return;
    reset();
    onClose();
  };

  const updateItem = (key: string, patch: Partial<DraftItem>) => {
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...patch } : it)));
    if (error) setError(null);
    if (errorItemKey) setErrorItemKey(null);
  };

  const removeItem = (key: string) => {
    setItems((prev) => (prev.length > 1 ? prev.filter((it) => it.key !== key) : prev));
  };

  const addItem = () => {
    if (items.length >= MAX_ITEMS) return;
    setItems((prev) => [...prev, _newDraft()]);
  };

  const handleSubmit = async () => {
    const valid = items
      .map((it) => ({ ...it, name: it.name.trim() }))
      .filter((it) => it.name.length > 0);

    if (valid.length === 0) {
      setError('Add at least one item with a name');
      setErrorItemKey(null);
      return;
    }

    const badPrice = valid.find((it) => {
      if (!it.price.trim()) return false;
      const n = Number(it.price);
      return Number.isNaN(n) || n < 0;
    });
    if (badPrice) {
      setError('Enter a valid price');
      setErrorItemKey(badPrice.key);
      return;
    }

    setSubmitting(true);
    setError(null);
    setErrorItemKey(null);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      const payload: MenuItemSubmission[] = valid.map((it) => ({
        name: it.name,
        category: it.category.trim() || null,
        price: it.price.trim() ? Number(it.price) : null,
        description: it.description.trim() || null,
      }));
      await submitMenu(placeId, payload);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      reset();
      onSubmitted?.();
      onClose();
    } catch (err: any) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      const status = err?.response?.status;
      if (status === 401) {
        setError('Sign in to submit a menu');
      } else if (status === 404) {
        setError("Couldn't find this place");
      } else if (status === 429) {
        setError("You're doing that too fast — wait a moment and try again.");
      } else {
        setError("Couldn't submit that menu. Try again.");
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
          <Text style={styles.title}>Add menu items</Text>
          <Text style={styles.body}>
            Know what they serve? Add a few items and we'll review them before
            they go live.
          </Text>
        </View>

        <ScrollView style={styles.list} keyboardShouldPersistTaps="handled">
          {items.map((item, idx) => (
            <View key={item.key} style={styles.itemCard}>
              <View style={styles.itemHeader}>
                <Text style={styles.itemIndex}>Item {idx + 1}</Text>
                {items.length > 1 ? (
                  <TouchableOpacity
                    onPress={() => removeItem(item.key)}
                    accessibilityRole="button"
                    accessibilityLabel={`Remove item ${idx + 1}`}
                    style={styles.removeBtn}
                  >
                    <Ionicons name="trash-outline" size={16} color={Colors.textMuted} />
                  </TouchableOpacity>
                ) : null}
              </View>

              <TextInput
                style={styles.input}
                placeholder="Item name (e.g. Cheeseburger)"
                placeholderTextColor={Colors.textMuted}
                value={item.name}
                onChangeText={(v) => updateItem(item.key, { name: v })}
                editable={!submitting}
                accessibilityLabel={`Item ${idx + 1} name`}
              />

              <View style={styles.row}>
                <TextInput
                  style={[styles.input, styles.inputHalf]}
                  placeholder="Category (optional)"
                  placeholderTextColor={Colors.textMuted}
                  value={item.category}
                  onChangeText={(v) => updateItem(item.key, { category: v })}
                  editable={!submitting}
                  accessibilityLabel={`Item ${idx + 1} category`}
                />
                <TextInput
                  style={[styles.input, styles.inputHalf]}
                  placeholder="Price (optional)"
                  placeholderTextColor={Colors.textMuted}
                  value={item.price}
                  onChangeText={(v) => updateItem(item.key, { price: v })}
                  keyboardType="decimal-pad"
                  editable={!submitting}
                  accessibilityLabel={`Item ${idx + 1} price`}
                />
              </View>

              {errorItemKey === item.key ? (
                <Text style={styles.itemError}>{error}</Text>
              ) : null}

              <TextInput
                style={styles.input}
                placeholder="Description (optional)"
                placeholderTextColor={Colors.textMuted}
                value={item.description}
                onChangeText={(v) => updateItem(item.key, { description: v })}
                editable={!submitting}
                accessibilityLabel={`Item ${idx + 1} description`}
              />
            </View>
          ))}

          <TouchableOpacity
            style={styles.addItemBtn}
            onPress={addItem}
            disabled={submitting || items.length >= MAX_ITEMS}
            accessibilityRole="button"
            accessibilityLabel="Add another item"
          >
            <Ionicons name="add" size={16} color={Colors.primary} />
            <Text style={styles.addItemText}>Add another item</Text>
          </TouchableOpacity>
        </ScrollView>

        {error && !errorItemKey ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.submitBtn, submitting && styles.submitBtnDisabled]}
          onPress={handleSubmit}
          disabled={submitting}
          activeOpacity={0.85}
          accessibilityRole="button"
          accessibilityLabel="Submit menu for review"
        >
          {submitting ? (
            <ActivityIndicator color={Colors.background} size="small" />
          ) : (
            <Text style={styles.submitBtnText}>Submit for review</Text>
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
    maxHeight: '85%',
    paddingBottom: 24,
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
    paddingBottom: Spacing.md,
  },
  title: { fontSize: 22, fontWeight: '800', color: Colors.text, marginBottom: Spacing.sm },
  body: { fontSize: 14, color: Colors.textSecondary, lineHeight: 20 },
  list: { paddingHorizontal: Spacing.xl },
  itemCard: {
    gap: Spacing.sm,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surfaceElevated,
  },
  itemHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  itemIndex: {
    fontSize: 11,
    fontWeight: '800',
    color: Colors.textMuted,
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  removeBtn: { padding: 6, minWidth: 32, minHeight: 32, alignItems: 'center', justifyContent: 'center' },
  row: { flexDirection: 'row', gap: Spacing.sm },
  inputHalf: { flex: 1 },
  input: {
    height: 48,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    paddingHorizontal: Spacing.md,
    color: Colors.text,
    fontSize: 14,
  },
  addItemBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 12,
    marginBottom: Spacing.md,
  },
  addItemText: { color: Colors.primary, fontSize: 14, fontWeight: '700' },
  error: {
    color: Colors.error,
    fontSize: 13,
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.sm,
  },
  itemError: {
    color: Colors.error,
    fontSize: 12,
    marginTop: -Spacing.xs,
    marginBottom: Spacing.sm,
  },
  submitBtn: {
    marginTop: Spacing.md,
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
