import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { Colors, Radius, Spacing, Typography } from '../src/constants/colors';
import { useAuthStore } from '../src/stores/authStore';
import { usePostingDraftStore, DraftIntent, DraftReaction, DraftVisibility } from '../src/stores/postingDraftStore';
import { useToast } from '../src/hooks/useToast';
import { ALLOWED_UPLOAD_TYPES, UploadContentType, confirmUpload, requestUpload, uploadToSignedUrl, validateUploadSize } from '../src/api/upload';
import { VideoContentType, confirmVideoUpload, requestVideoUpload, uploadVideoToSignedUrl } from '../src/api/videos';
import { createContribution } from '../src/api/contributions';

function imageContentType(mime?: string): UploadContentType {
  return mime && (ALLOWED_UPLOAD_TYPES as readonly string[]).includes(mime) ? mime as UploadContentType : 'image/jpeg';
}
function videoContentType(uri: string): VideoContentType {
  const ext = uri.split('.').pop()?.toLowerCase();
  if (ext === 'mov') return 'video/quicktime';
  if (ext === 'webm') return 'video/webm';
  return 'video/mp4';
}

export default function PostingComposerScreen() {
  const router = useRouter();
  const { draftId } = useLocalSearchParams<{ draftId?: string }>();
  const user = useAuthStore((s) => s.user);
  const draft = usePostingDraftStore((s) => s.drafts.find((d) => d.id === draftId));
  const actions = usePostingDraftStore();
  const toast = useToast((s) => s.show);
  const [submitting, setSubmitting] = useState(false);

  const canCommit = useMemo(() => {
    if (!draft || !user || draft.ownerId !== user.id || draft.restaurantRef.type !== 'place' || !draft.intent) return false;
    if (draft.intent === 'private_log') return draft.visibility === 'private';
    return draft.visibility === 'connections' || draft.visibility === 'public';
  }, [draft, user]);

  if (!draft || !user || draft.ownerId !== user.id) {
    return <View style={styles.center}><Text style={styles.title}>Draft unavailable</Text><Text style={styles.muted}>This draft is missing or belongs to another account.</Text></View>;
  }

  const placeReady = draft.restaurantRef.type === 'place';

  async function commit() {
    if (!draft || draft.restaurantRef.type !== 'place' || !draft.intent || !draft.visibility || !canCommit) return;
    setSubmitting(true);
    try {
      let mediaId = draft.uploadedMediaId;
      if (!mediaId) {
        if (draft.kind === 'photo') {
          if (!draft.fileSize) throw new Error("Couldn't read this photo's file size");
          const contentType = imageContentType(draft.mimeType);
          const requested = await requestUpload({ place_id: draft.restaurantRef.placeId, content_type: contentType, file_size_mb: validateUploadSize(draft.fileSize), photo_type: 'food' });
          await uploadToSignedUrl(requested.upload_url, draft.localUri, contentType);
          await confirmUpload(requested.image_id);
          mediaId = requested.image_id;
        } else {
          const contentType = videoContentType(draft.localUri);
          const requested = await requestVideoUpload({ place_id: draft.restaurantRef.placeId, content_type: contentType, client_id: draft.id });
          await uploadVideoToSignedUrl(requested.upload_url, draft.localUri, contentType);
          await confirmVideoUpload(requested.video_id);
          mediaId = requested.video_id;
        }
        actions.setUploadedMediaId(draft.id, mediaId);
      }

      await createContribution({
        client_id: draft.id,
        place_id: draft.restaurantRef.placeId,
        intent: draft.intent,
        reaction: draft.reaction,
        caption: draft.caption.trim() || null,
        visibility: draft.visibility,
        occurred_at: draft.occurredAt,
        image_id: draft.kind === 'photo' ? mediaId : null,
        video_id: draft.kind === 'video' ? mediaId : null,
      });
      await actions.deleteDraft(draft.id);
      toast(draft.intent === 'private_log' ? 'Saved to your food history' : 'Post submitted');
      router.replace('/(tabs)');
    } catch (error) {
      toast(error instanceof Error ? error.message : "Couldn't finish this contribution. Your draft is still saved.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text style={styles.eyebrow}>CRAVE</Text>
      <Text style={styles.title}>Record the meal</Text>
      <Text style={styles.muted}>Your media stays private until you explicitly finish this screen.</Text>

      <View style={styles.mediaCard}>
        {draft.kind === 'photo' ? <Image source={{ uri: draft.localUri }} style={styles.preview} accessibilityLabel="Selected food photo" /> : <View style={[styles.preview, styles.videoPreview]}><Ionicons name="videocam" size={36} color={Colors.text} /><Text style={styles.muted}>Video ready</Text></View>}
      </View>

      <Section title="Restaurant">
        <Text style={styles.value}>{draft.restaurantRef.type === 'place' ? 'Restaurant confirmed' : draft.restaurantRef.type === 'candidate' ? `${draft.restaurantRef.displayName} · waiting for confirmation` : 'Choose a restaurant first'}</Text>
        {!placeReady ? <Pressable style={styles.secondaryButton} onPress={() => router.push({ pathname: '/add-spot', params: { draftId: draft.id } })}><Text style={styles.secondaryLabel}>Choose restaurant</Text></Pressable> : null}
      </Section>

      <Section title="Keep it private or post it">
        <Choice label="Private log" selected={draft.intent === 'private_log'} onPress={() => actions.setDraftIntent(draft.id, 'private_log')} />
        <Choice label="Social post" selected={draft.intent === 'social_post'} onPress={() => actions.setDraftIntent(draft.id, 'social_post')} />
      </Section>

      <Section title="Quick take">
        <View style={styles.row}>
          {([['loved', 'Loved it'], ['good', 'Good'], ['not_for_me', 'Not for me']] as const).map(([value, label]) => <Choice key={value} compact label={label} selected={draft.reaction === value} onPress={() => actions.setDraftReaction(draft.id, draft.reaction === value ? null : value as DraftReaction)} />)}
        </View>
      </Section>

      <Section title="Caption · optional">
        <TextInput value={draft.caption} onChangeText={(v) => actions.setDraftCaption(draft.id, v.slice(0, 2000))} placeholder="What stood out?" placeholderTextColor={Colors.textSecondary} multiline style={styles.input} accessibilityLabel="Optional caption" />
      </Section>

      {draft.intent === 'social_post' ? (
        <Section title="Who can see this">
          <Choice label="People I follow" selected={draft.visibility === 'connections'} onPress={() => actions.setDraftVisibility(draft.id, 'connections' as DraftVisibility)} />
          <Choice label="Public" selected={draft.visibility === 'public'} onPress={() => actions.setDraftVisibility(draft.id, 'public' as DraftVisibility)} />
        </Section>
      ) : null}

      <Pressable disabled={!canCommit || submitting} onPress={() => void commit()} style={[styles.primaryButton, (!canCommit || submitting) && styles.disabled]} accessibilityRole="button" accessibilityLabel={draft.intent === 'social_post' ? 'Post meal' : 'Save private food log'}>
        {submitting ? <ActivityIndicator color={Colors.background} /> : <Text style={styles.primaryLabel}>{draft.intent === 'social_post' ? 'Post' : draft.intent === 'private_log' ? 'Save privately' : 'Choose private or post'}</Text>}
      </Pressable>
      <Text style={styles.footer}>No likes, follower counts, or engagement score is created from this action.</Text>
    </ScrollView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) { return <View style={styles.section}><Text style={styles.sectionTitle}>{title}</Text>{children}</View>; }
function Choice({ label, selected, onPress, compact = false }: { label: string; selected: boolean; onPress: () => void; compact?: boolean }) {
  return <Pressable onPress={onPress} accessibilityRole="button" accessibilityState={{ selected }} style={[styles.choice, compact && styles.choiceCompact, selected && styles.choiceSelected]}><Text style={[styles.choiceText, selected && styles.choiceTextSelected]}>{label}</Text></Pressable>;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background }, content: { padding: Spacing.lg, paddingBottom: 56 }, center: { flex: 1, backgroundColor: Colors.background, alignItems: 'center', justifyContent: 'center', padding: Spacing.xl, gap: Spacing.sm },
  eyebrow: { ...Typography.caption, color: Colors.primary, fontWeight: '800', letterSpacing: 1.2 }, title: { ...Typography.title, color: Colors.text, marginTop: Spacing.xs }, muted: { ...Typography.body, color: Colors.textSecondary, lineHeight: 20 },
  mediaCard: { marginTop: Spacing.lg, borderRadius: Radius.card, overflow: 'hidden', backgroundColor: Colors.surface }, preview: { width: '100%', aspectRatio: 4 / 3 }, videoPreview: { alignItems: 'center', justifyContent: 'center', gap: Spacing.sm },
  section: { marginTop: Spacing.xl, gap: Spacing.sm }, sectionTitle: { ...Typography.body, color: Colors.text, fontWeight: '800' }, value: { ...Typography.body, color: Colors.textSecondary }, row: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  choice: { minHeight: 48, borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, justifyContent: 'center', paddingHorizontal: Spacing.md }, choiceCompact: { minHeight: 44 }, choiceSelected: { borderColor: Colors.primary }, choiceText: { ...Typography.body, color: Colors.textSecondary, fontWeight: '700' }, choiceTextSelected: { color: Colors.text },
  input: { minHeight: 96, borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, color: Colors.text, padding: Spacing.md, textAlignVertical: 'top', ...Typography.body },
  secondaryButton: { minHeight: 44, borderRadius: Radius.pill, borderWidth: 1, borderColor: Colors.border, alignItems: 'center', justifyContent: 'center', paddingHorizontal: Spacing.md, alignSelf: 'flex-start' }, secondaryLabel: { ...Typography.body, color: Colors.text, fontWeight: '700' },
  primaryButton: { minHeight: 52, borderRadius: Radius.pill, backgroundColor: Colors.primary, alignItems: 'center', justifyContent: 'center', marginTop: Spacing.xl }, primaryLabel: { ...Typography.body, color: Colors.background, fontWeight: '900' }, disabled: { opacity: 0.45 }, footer: { ...Typography.caption, color: Colors.textSecondary, textAlign: 'center', marginTop: Spacing.md },
});
