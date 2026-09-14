// app/uploads.tsx
//
// Offline-upload visibility. videoQueueStore and postingDraftStore have
// always been able to queue/retry/delete local media durably, but neither
// store had any UI surface -- a failed video or an unresolved draft just
// sat invisibly until the next foreground sync pass tried it again, with
// no way for the user to see it, retry it sooner, or clear it. This screen
// wires the already-built (but previously dead) retryFailedVideo/
// deleteFailedVideo/deleteDraft/attachDraftToPlace-retry into real UI.
import React, { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, Radius, Typography } from '../src/constants/colors';
import { EmptyState } from '../src/components/EmptyState';
import { useAuthStore } from '../src/stores/authStore';
import { useVideoQueueStore, QueuedVideo } from '../src/stores/videoQueueStore';
import { usePostingDraftStore, PostingDraft } from '../src/stores/postingDraftStore';

const VIDEO_STATE_COPY: Record<QueuedVideo['syncState'], string> = {
  recorded: 'Queued — will upload automatically',
  requesting_url: 'Uploading…',
  uploading: 'Uploading…',
  completing: 'Finishing up…',
  synced: 'Uploaded',
  failed: "Couldn't upload",
  missing_local_file: 'Recording no longer available',
};

function isVideoInProgress(state: QueuedVideo['syncState']): boolean {
  return state === 'requesting_url' || state === 'uploading' || state === 'completing';
}

function isVideoTerminalFailure(state: QueuedVideo['syncState']): boolean {
  return state === 'failed' || state === 'missing_local_file';
}

function draftStatusCopy(draft: PostingDraft): string {
  if (draft.outcome === 'attaching') return 'Saving…';
  if (draft.outcome === 'failed') return draft.lastError ?? "Couldn't save this to the place";
  if (draft.restaurantRef.type === 'candidate') {
    return `Waiting for "${draft.restaurantRef.displayName}" to be confirmed`;
  }
  return 'Waiting for you to identify the restaurant';
}

export default function UploadsScreen() {
  const user = useAuthStore((s) => s.user);
  const videos = useVideoQueueStore((s) => s.videos);
  const retryFailedVideo = useVideoQueueStore((s) => s.retryFailedVideo);
  const deleteFailedVideo = useVideoQueueStore((s) => s.deleteFailedVideo);
  const runSyncPass = useVideoQueueStore((s) => s.runSyncPass);
  const drafts = usePostingDraftStore((s) => s.drafts);
  const attachDraftToPlace = usePostingDraftStore((s) => s.attachDraftToPlace);
  const deleteDraft = usePostingDraftStore((s) => s.deleteDraft);
  const [retryingDraftId, setRetryingDraftId] = useState<string | null>(null);

  // 'synced' videos are pruned by the store itself on the next sync pass
  // (see videoQueueStore.ts) -- excluded here too so a video doesn't
  // flash "Uploaded" in this list for the brief window before that
  // pruning runs.
  const myVideos = useMemo(
    () => (user ? videos.filter((v) => v.uploadedBy === user.id && v.syncState !== 'synced') : []),
    [videos, user]
  );
  const myDrafts = useMemo(
    () => (user ? drafts.filter((d) => d.ownerId === user.id) : []),
    [drafts, user]
  );

  const handleRetryVideo = useCallback(
    (id: string) => {
      if (!user) return;
      retryFailedVideo(id);
      runSyncPass(user.id).catch(() => {});
    },
    [retryFailedVideo, runSyncPass, user]
  );

  const handleDeleteVideo = useCallback(
    (id: string) => {
      Alert.alert('Delete this video?', "This can't be undone.", [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: () => { void deleteFailedVideo(id); } },
      ]);
    },
    [deleteFailedVideo]
  );

  const handleRetryDraft = useCallback(
    async (draft: PostingDraft) => {
      // Guarded by the calling JSX (only rendered for restaurantRef.type
      // === 'place'), but narrowed again here for TS and to make the
      // invariant explicit rather than assumed.
      if (draft.restaurantRef.type !== 'place' || !user) return;
      setRetryingDraftId(draft.id);
      try {
        await attachDraftToPlace(draft.id, draft.restaurantRef.placeId, user.id);
      } finally {
        setRetryingDraftId(null);
      }
    },
    [attachDraftToPlace, user]
  );

  const handleDeleteDraft = useCallback(
    (id: string) => {
      Alert.alert('Delete this upload?', "This can't be undone.", [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: () => { void deleteDraft(id); } },
      ]);
    },
    [deleteDraft]
  );

  if (!user) {
    return (
      <EmptyState
        icon="cloud-upload-outline"
        title="Sign in to see your uploads"
        body="Queued and failed photo/video uploads will appear here."
      />
    );
  }

  if (myVideos.length === 0 && myDrafts.length === 0) {
    return (
      <EmptyState
        icon="cloud-done-outline"
        title="Nothing pending"
        body="Every photo and video you've captured has been saved."
      />
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {myVideos.length > 0 ? (
        <>
          <Text style={styles.sectionTitle}>VIDEOS</Text>
          <View style={styles.card}>
            {myVideos.map((video, index) => {
              const failed = isVideoTerminalFailure(video.syncState);
              return (
                <React.Fragment key={video.id}>
                  {index > 0 ? <View style={styles.divider} /> : null}
                  <View style={styles.row}>
                    <View style={styles.rowIcon}>
                      {isVideoInProgress(video.syncState) ? (
                        <ActivityIndicator size="small" color={Colors.brand} />
                      ) : (
                        <Ionicons
                          name={failed ? 'alert-circle-outline' : 'videocam-outline'}
                          size={18}
                          color={failed ? Colors.error : Colors.textSecondary}
                        />
                      )}
                    </View>
                    <View style={styles.rowBody}>
                      <Text style={styles.rowLabel}>Video</Text>
                      <Text style={[styles.rowSub, failed ? styles.rowSubError : null]}>
                        {video.syncState === 'failed' && video.lastError
                          ? video.lastError
                          : VIDEO_STATE_COPY[video.syncState]}
                      </Text>
                    </View>
                    {video.syncState === 'failed' ? (
                      <TouchableOpacity
                        style={styles.actionButton}
                        onPress={() => handleRetryVideo(video.id)}
                        accessibilityRole="button"
                        accessibilityLabel="Retry upload"
                      >
                        <Text style={styles.actionButtonText}>Retry</Text>
                      </TouchableOpacity>
                    ) : null}
                    {failed ? (
                      <TouchableOpacity
                        style={styles.iconButton}
                        onPress={() => handleDeleteVideo(video.id)}
                        accessibilityRole="button"
                        accessibilityLabel="Delete video"
                      >
                        <Ionicons name="trash-outline" size={18} color={Colors.error} />
                      </TouchableOpacity>
                    ) : null}
                  </View>
                </React.Fragment>
              );
            })}
          </View>
        </>
      ) : null}

      {myDrafts.length > 0 ? (
        <>
          <Text style={styles.sectionTitle}>PHOTOS &amp; VIDEOS AWAITING A RESTAURANT</Text>
          <View style={styles.card}>
            {myDrafts.map((draft, index) => {
              const isRetrying = retryingDraftId === draft.id;
              const canRetry = draft.outcome === 'failed' && draft.restaurantRef.type === 'place';
              return (
                <React.Fragment key={draft.id}>
                  {index > 0 ? <View style={styles.divider} /> : null}
                  <View style={styles.row}>
                    <View style={styles.rowIcon}>
                      {draft.outcome === 'attaching' || isRetrying ? (
                        <ActivityIndicator size="small" color={Colors.brand} />
                      ) : (
                        <Ionicons
                          name={draft.kind === 'video' ? 'videocam-outline' : 'image-outline'}
                          size={18}
                          color={draft.outcome === 'failed' ? Colors.error : Colors.textSecondary}
                        />
                      )}
                    </View>
                    <View style={styles.rowBody}>
                      <Text style={styles.rowLabel}>{draft.kind === 'video' ? 'Video' : 'Photo'}</Text>
                      <Text style={[styles.rowSub, draft.outcome === 'failed' ? styles.rowSubError : null]}>
                        {draftStatusCopy(draft)}
                      </Text>
                    </View>
                    {canRetry ? (
                      <TouchableOpacity
                        style={styles.actionButton}
                        disabled={isRetrying}
                        onPress={() => { void handleRetryDraft(draft); }}
                        accessibilityRole="button"
                        accessibilityLabel="Retry"
                      >
                        <Text style={styles.actionButtonText}>Retry</Text>
                      </TouchableOpacity>
                    ) : null}
                    <TouchableOpacity
                      style={styles.iconButton}
                      onPress={() => handleDeleteDraft(draft.id)}
                      accessibilityRole="button"
                      accessibilityLabel="Delete"
                    >
                      <Ionicons name="trash-outline" size={18} color={Colors.error} />
                    </TouchableOpacity>
                  </View>
                </React.Fragment>
              );
            })}
          </View>
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { paddingBottom: 48 },
  sectionTitle: {
    fontSize: 10,
    fontWeight: '800',
    color: Colors.textSecondary,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  card: {
    marginHorizontal: Spacing.lg,
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.border,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    gap: Spacing.md,
    minHeight: 56,
  },
  rowIcon: {
    width: 32,
    height: 32,
    borderRadius: Radius.sm,
    backgroundColor: Colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowBody: { flex: 1, gap: Spacing.xs },
  rowLabel: { fontSize: 15, fontWeight: '600', color: Colors.text },
  rowSub: { fontSize: 12, color: Colors.textSecondary },
  rowSubError: { color: Colors.error },
  divider: { height: 1, backgroundColor: Colors.border, marginLeft: 56 },
  actionButton: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: Radius.pill,
    backgroundColor: Colors.actionPrimary,
    minHeight: 32,
    justifyContent: 'center',
  },
  actionButtonText: { color: Colors.onActionPrimary, fontSize: 13, fontWeight: '700' },
  iconButton: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
