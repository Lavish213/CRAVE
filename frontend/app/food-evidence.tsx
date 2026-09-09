import React, { useState } from 'react';
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';

import { Colors, Radius, Spacing, Typography } from '../src/constants/colors';
import { useAuthStore } from '../src/stores/authStore';
import { AuthSheet } from '../src/components/AuthSheet';
import { DraftMediaKind, usePostingDraftStore } from '../src/stores/postingDraftStore';
import { useToast } from '../src/hooks/useToast';

export default function FoodEvidenceScreen() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const drafts = usePostingDraftStore((s) => s.drafts.filter((d) => d.ownerId === user?.id));
  const createDraft = usePostingDraftStore((s) => s.createDraftFromCapture);
  const toast = useToast((s) => s.show);
  const [busy, setBusy] = useState(false);
  const [authVisible, setAuthVisible] = useState(false);

  if (!user) {
    return <View style={styles.center}><Ionicons name="person-circle-outline" size={44} color={Colors.textSecondary} /><Text style={styles.title}>Sign in to record food</Text><Text style={styles.muted}>Your private logs and posts stay attached to your account.</Text><Pressable style={styles.primary} onPress={() => setAuthVisible(true)}><Text style={styles.primaryLabel}>Sign in</Text></Pressable><AuthSheet visible={authVisible} onClose={() => setAuthVisible(false)} reason="default" /></View>;
  }

  async function persist(kind: DraftMediaKind, asset: ImagePicker.ImagePickerAsset) {
    setBusy(true);
    try {
      const draft = await createDraft({ ownerId: user!.id, sourceUri: asset.uri, kind, mimeType: asset.mimeType, fileSize: asset.fileSize });
      router.push({ pathname: '/posting-restaurant', params: { draftId: draft.id } });
    } catch (error) {
      toast(error instanceof Error ? error.message : "Couldn't save that media");
    } finally { setBusy(false); }
  }

  async function camera(kind: DraftMediaKind) {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) { Alert.alert('Camera unavailable', 'You can still choose media from your library.'); return; }
    const result = await ImagePicker.launchCameraAsync({ mediaTypes: kind === 'photo' ? ['images'] : ['videos'], allowsEditing: false, quality: kind === 'photo' ? 0.9 : 1 });
    if (!result.canceled && result.assets[0]) await persist(kind, result.assets[0]);
  }

  async function library() {
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images', 'videos'], allowsEditing: false, quality: 0.9 });
    if (!result.canceled && result.assets[0]) await persist(result.assets[0].type === 'video' ? 'video' : 'photo', result.assets[0]);
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>RECORD FOOD</Text><Text style={styles.title}>Start with what you ate</Text>
      <Text style={styles.muted}>Capture once. Nothing uploads or publishes until you identify the restaurant and explicitly finish the composer.</Text>

      <View style={styles.actions}>
        <Action icon="camera-outline" label="Take photo" onPress={() => void camera('photo')} disabled={busy} />
        <Action icon="videocam-outline" label="Record video" onPress={() => void camera('video')} disabled={busy} />
        <Action icon="images-outline" label="Choose from library" onPress={() => void library()} disabled={busy} />
      </View>
      {busy ? <ActivityIndicator style={styles.spinner} color={Colors.primary} /> : null}

      {drafts.length > 0 ? <View style={styles.drafts}><Text style={styles.sectionTitle}>Saved drafts</Text>{drafts.map((draft) => <Pressable key={draft.id} style={styles.draft} onPress={() => router.push({ pathname: draft.restaurantRef.type === 'place' ? '/posting-composer' : '/posting-restaurant', params: { draftId: draft.id } })} accessibilityRole="button" accessibilityLabel={`Resume ${draft.kind} draft`}><Ionicons name={draft.kind === 'photo' ? 'image-outline' : 'videocam-outline'} size={20} color={Colors.primary} /><View style={styles.draftCopy}><Text style={styles.draftTitle}>{draft.kind === 'photo' ? 'Photo draft' : 'Video draft'}</Text><Text style={styles.caption}>{draft.restaurantRef.type === 'place' ? 'Restaurant selected · finish your log or post' : draft.restaurantRef.type === 'candidate' ? `Waiting on ${draft.restaurantRef.displayName}` : 'Restaurant not selected yet'}</Text></View><Ionicons name="chevron-forward" size={18} color={Colors.textSecondary} /></Pressable>)}</View> : null}

      <Text style={styles.privacy}>Private log and social post are separate choices. CRAVE never silently publishes a capture.</Text>
    </ScrollView>
  );
}

function Action({ icon, label, onPress, disabled }: { icon: React.ComponentProps<typeof Ionicons>['name']; label: string; onPress: () => void; disabled: boolean }) {
  return <Pressable disabled={disabled} onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={({ pressed }) => [styles.action, pressed && styles.pressed, disabled && styles.disabled]}><Ionicons name={icon} size={24} color={Colors.text} /><Text style={styles.actionLabel}>{label}</Text></Pressable>;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background }, content: { padding: Spacing.lg, paddingBottom: 56 }, center: { flex: 1, backgroundColor: Colors.background, alignItems: 'center', justifyContent: 'center', padding: Spacing.xl, gap: Spacing.sm },
  eyebrow: { ...Typography.caption, color: Colors.primary, fontWeight: '800', letterSpacing: 1.1 }, title: { ...Typography.title, color: Colors.text, marginTop: Spacing.xs }, muted: { ...Typography.body, color: Colors.textSecondary, textAlign: 'center', lineHeight: 20 },
  actions: { marginTop: Spacing.xl, gap: Spacing.sm }, action: { minHeight: 58, borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, flexDirection: 'row', alignItems: 'center', gap: Spacing.md, paddingHorizontal: Spacing.lg }, actionLabel: { ...Typography.body, color: Colors.text, fontWeight: '800' }, pressed: { opacity: 0.82 }, disabled: { opacity: 0.5 }, spinner: { marginTop: Spacing.md },
  drafts: { marginTop: Spacing.xl, gap: Spacing.sm }, sectionTitle: { ...Typography.body, color: Colors.text, fontWeight: '800' }, draft: { minHeight: 64, borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, padding: Spacing.md, flexDirection: 'row', alignItems: 'center', gap: Spacing.sm }, draftCopy: { flex: 1 }, draftTitle: { ...Typography.body, color: Colors.text, fontWeight: '700' }, caption: { ...Typography.caption, color: Colors.textSecondary, marginTop: 2 },
  primary: { minHeight: 48, borderRadius: Radius.pill, backgroundColor: Colors.primary, alignItems: 'center', justifyContent: 'center', paddingHorizontal: Spacing.lg, marginTop: Spacing.sm }, primaryLabel: { ...Typography.body, color: Colors.background, fontWeight: '900' }, privacy: { ...Typography.caption, color: Colors.textSecondary, textAlign: 'center', marginTop: Spacing.xl },
});
