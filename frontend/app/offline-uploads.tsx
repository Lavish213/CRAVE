import React, { useMemo, useState } from 'react';
import {
  Alert,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';

import { Colors, Radius, Shadows, Spacing, Typography } from '../src/constants/colors';
import {
  useVideoQueueStore,
} from '../src/stores/videoQueueStore';
import type { QueuedVideo, VideoSyncState } from '../src/stores/videoQueueStore';
import { useAuthStore } from '../src/stores/authStore';
import { useToast } from '../src/hooks/useToast';

const STATUS_COPY: Record<VideoSyncState, { label: string; detail: string; icon: React.ComponentProps<typeof Ionicons>['name'] }> = {
  recorded: {
    label: 'Waiting to post',
    detail: 'Saved on this phone. CRAVE will post it when sync runs.',
    icon: 'time-outline',
  },
  requesting_url: {
    label: 'Preparing upload',
    detail: 'Getting a secure upload slot.',
    icon: 'cloud-upload-outline',
  },
  uploading: {
    label: 'Uploading',
    detail: 'Sending the original clip.',
    icon: 'cloud-upload-outline',
  },
  completing: {
    label: 'Finalizing',
    detail: 'Asking CRAVE to process the clip.',
    icon: 'sparkles-outline',
  },
  synced: {
    label: 'Posted for review',
    detail: 'Uploaded. CRAVE is processing or reviewing it now.',
    icon: 'checkmark-circle-outline',
  },
  failed: {
    label: 'Needs retry',
    detail: 'The local clip is still saved. Retry when your connection is better.',
    icon: 'alert-circle-outline',
  },
  missing_local_file: {
    label: 'File missing',
    detail: 'The local clip is gone, so this upload cannot be recovered.',
    icon: 'trash-outline',
  },
};

function queueSummary(videos: QueuedVideo[]): string {
  const active = videos.filter((v) =>
    ['recorded', 'requesting_url', 'uploading', 'completing'].includes(v.syncState)
  ).length;
  const needsAttention = videos.filter((v) =>
    v.syncState === 'failed' || v.syncState === 'missing_local_file'
  ).length;
  const done = videos.filter((v) => v.syncState === 'synced').length;
  if (videos.length === 0) return 'No queued video uploads.';
  return [
    active ? `${active} waiting` : null,
    needsAttention ? `${needsAttention} need attention` : null,
    done ? `${done} posted for review` : null,
  ].filter(Boolean).join(' · ');
}

function formatAge(createdAt: number): string {
  const minutes = Math.max(0, Math.floor((Date.now() - createdAt) / 60_000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function progressFor(video: QueuedVideo): number {
  if (typeof video.progressPct === 'number') return video.progressPct;
  if (video.syncState === 'synced') return 1;
  if (video.syncState === 'recorded') return 0;
  return 0;
}

function QueueCard({
  video,
  onRetry,
  onDelete,
}: {
  video: QueuedVideo;
  onRetry: (id: string) => void;
  onDelete: (video: QueuedVideo) => void;
}) {
  const copy = STATUS_COPY[video.syncState];
  const progress = progressFor(video);
  const canRetry = video.syncState === 'failed';
  const canDelete = video.syncState === 'failed' || video.syncState === 'missing_local_file';
  const tone =
    video.syncState === 'failed' || video.syncState === 'missing_local_file'
      ? Colors.error
      : video.syncState === 'synced'
        ? Colors.success
        : Colors.brand;

  return (
    <View style={styles.queueCard}>
      <View style={styles.queueHeader}>
        <View style={[styles.statusIcon, { borderColor: tone }]}>
          <Ionicons name={copy.icon} size={18} color={tone} />
        </View>
        <View style={styles.queueTitleWrap}>
          <Text style={styles.queueTitle}>{copy.label}</Text>
          <Text style={styles.queueMeta}>{formatAge(video.createdAt)} · {video.contentType}</Text>
        </View>
      </View>

      <Text style={styles.queueDetail}>{copy.detail}</Text>
      {video.lastError ? <Text style={styles.errorText}>{video.lastError}</Text> : null}

      {video.syncState !== 'failed' && video.syncState !== 'missing_local_file' ? (
        <View style={styles.progressTrack} accessibilityLabel={`${Math.round(progress * 100)} percent complete`}>
          <View style={[styles.progressFill, { width: `${Math.max(4, Math.round(progress * 100))}%` }]} />
        </View>
      ) : null}

      {canRetry || canDelete ? (
        <View style={styles.actions}>
          {canRetry ? (
            <TouchableOpacity
              style={[styles.actionButton, styles.primaryAction]}
              onPress={() => onRetry(video.id)}
              accessibilityRole="button"
              accessibilityLabel="Retry upload"
            >
              <Text style={styles.primaryActionText}>Retry</Text>
            </TouchableOpacity>
          ) : null}
          {canDelete ? (
            <TouchableOpacity
              style={[styles.actionButton, styles.secondaryAction]}
              onPress={() => onDelete(video)}
              accessibilityRole="button"
              accessibilityLabel="Remove upload from queue"
            >
              <Text style={styles.secondaryActionText}>
                {video.syncState === 'missing_local_file' ? 'Remove' : 'Delete'}
              </Text>
            </TouchableOpacity>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

export default function OfflineUploadsScreen() {
  const user = useAuthStore((s) => s.user);
  const toast = useToast((s) => s.show);
  const videos = useVideoQueueStore((s) => s.videos);
  const autoSyncEnabled = useVideoQueueStore((s) => s.autoSyncEnabled);
  const setAutoSyncEnabled = useVideoQueueStore((s) => s.setAutoSyncEnabled);
  const runSyncPass = useVideoQueueStore((s) => s.runSyncPass);
  const retryFailedVideo = useVideoQueueStore((s) => s.retryFailedVideo);
  const deleteFailedVideo = useVideoQueueStore((s) => s.deleteFailedVideo);
  const [syncing, setSyncing] = useState(false);

  const visibleVideos = useMemo(() => {
    if (!user?.id) return [];
    return videos.filter((v) => v.uploadedBy === user.id);
  }, [videos, user?.id]);

  const handleSyncNow = async () => {
    if (!user?.id) {
      toast('Sign in to sync queued uploads.');
      return;
    }
    setSyncing(true);
    try {
      await runSyncPass(user.id, { force: true });
      toast('Upload queue checked.');
    } catch {
      toast("Couldn't sync right now. Your clips are still saved.");
    } finally {
      setSyncing(false);
    }
  };

  const handleRetry = async (id: string) => {
    if (!user?.id) {
      toast('Sign in to retry queued uploads.');
      return;
    }
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    retryFailedVideo(id);
    setSyncing(true);
    try {
      await runSyncPass(user.id, { force: true });
    } finally {
      setSyncing(false);
    }
  };

  const handleDelete = (video: QueuedVideo) => {
    Alert.alert(
      video.syncState === 'missing_local_file' ? 'Remove this upload?' : 'Delete this saved clip?',
      video.syncState === 'missing_local_file'
        ? 'The local video is already gone. This only clears the queue entry.'
        : 'This removes the local video file from this phone. It cannot be uploaded later.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: video.syncState === 'missing_local_file' ? 'Remove' : 'Delete',
          style: 'destructive',
          onPress: () => {
            void deleteFailedVideo(video.id);
          },
        },
      ],
    );
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.eyebrow}>OFFLINE UPLOADS</Text>
        <Text style={styles.title}>Your queued food videos.</Text>
        <Text style={styles.subtitle}>
          Videos save on this phone first, then upload when CRAVE can sync them.
        </Text>
      </View>

      <View style={styles.summaryCard}>
        <View style={styles.summaryTop}>
          <View>
            <Text style={styles.summaryLabel}>Queue status</Text>
            <Text style={styles.summaryText}>{queueSummary(visibleVideos)}</Text>
          </View>
          <TouchableOpacity
            style={[styles.syncButton, syncing ? styles.disabledButton : null]}
            onPress={handleSyncNow}
            disabled={syncing}
            accessibilityRole="button"
            accessibilityLabel="Sync queued uploads now"
          >
            <Text style={styles.syncButtonText}>{syncing ? 'Syncing…' : 'Sync now'}</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.divider} />

        <View style={styles.settingRow}>
          <View style={styles.settingBody}>
            <Text style={styles.settingLabel}>Auto-sync videos</Text>
            <Text style={styles.settingCopy}>
              Turn this off if you want to wait for Wi‑Fi, then use Sync now when ready.
            </Text>
          </View>
          <Switch
            value={autoSyncEnabled}
            onValueChange={setAutoSyncEnabled}
            trackColor={{ false: Colors.border, true: Colors.brandSoft }}
            thumbColor={autoSyncEnabled ? Colors.brand : Colors.textSecondary}
            accessibilityLabel="Auto-sync videos"
          />
        </View>
      </View>

      {!user ? (
        <View style={styles.emptyCard}>
          <Ionicons name="person-circle-outline" size={32} color={Colors.textSecondary} />
          <Text style={styles.emptyTitle}>Sign in to manage uploads</Text>
          <Text style={styles.emptyCopy}>
            CRAVE keeps video uploads account-scoped so one person’s queued clips never post under another account.
          </Text>
        </View>
      ) : null}

      {user && visibleVideos.length === 0 ? (
        <View style={styles.emptyCard}>
          <Ionicons name="checkmark-circle-outline" size={32} color={Colors.success} />
          <Text style={styles.emptyTitle}>All caught up</Text>
          <Text style={styles.emptyCopy}>No food videos are waiting on this phone.</Text>
        </View>
      ) : null}

      {user ? visibleVideos.map((video) => (
        <QueueCard
          key={video.id}
          video={video}
          onRetry={handleRetry}
          onDelete={handleDelete}
        />
      )) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { paddingBottom: 48 },
  header: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.lg,
  },
  eyebrow: {
    ...Typography.micro,
    color: Colors.brand,
    fontWeight: '800',
    letterSpacing: 1.6,
  },
  title: {
    ...Typography.headline,
    color: Colors.text,
    marginTop: Spacing.xs,
  },
  subtitle: {
    ...Typography.body,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
  },
  summaryCard: {
    marginHorizontal: Spacing.lg,
    padding: Spacing.md,
    borderRadius: Radius.card,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    ...Shadows.card,
  },
  summaryTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  summaryLabel: {
    ...Typography.caption,
    color: Colors.textSecondary,
    fontWeight: '700',
  },
  summaryText: {
    ...Typography.body,
    color: Colors.text,
    marginTop: Spacing.xs,
  },
  syncButton: {
    minHeight: 44,
    paddingHorizontal: Spacing.md,
    borderRadius: Radius.full,
    backgroundColor: Colors.actionPrimary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  syncButtonText: {
    ...Typography.caption,
    color: Colors.onActionPrimary,
    fontWeight: '800',
  },
  disabledButton: { opacity: 0.6 },
  divider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.md,
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  settingBody: { flex: 1 },
  settingLabel: {
    ...Typography.label,
    color: Colors.text,
  },
  settingCopy: {
    ...Typography.caption,
    color: Colors.textSecondary,
    marginTop: Spacing.xs,
  },
  emptyCard: {
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.lg,
    padding: Spacing.lg,
    borderRadius: Radius.card,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    gap: Spacing.sm,
  },
  emptyTitle: {
    ...Typography.subtitle,
    color: Colors.text,
    textAlign: 'center',
  },
  emptyCopy: {
    ...Typography.body,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
  queueCard: {
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.lg,
    padding: Spacing.md,
    borderRadius: Radius.card,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    ...Shadows.card,
  },
  queueHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  statusIcon: {
    width: 36,
    height: 36,
    borderRadius: Radius.full,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.surfaceElevated,
  },
  queueTitleWrap: { flex: 1 },
  queueTitle: {
    ...Typography.label,
    color: Colors.text,
  },
  queueMeta: {
    ...Typography.caption,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  queueDetail: {
    ...Typography.body,
    color: Colors.textSecondary,
    marginTop: Spacing.md,
  },
  errorText: {
    ...Typography.caption,
    color: Colors.error,
    marginTop: Spacing.sm,
  },
  progressTrack: {
    height: 6,
    borderRadius: Radius.full,
    backgroundColor: Colors.surfaceElevated,
    marginTop: Spacing.md,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: Radius.full,
    backgroundColor: Colors.brand,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.md,
  },
  actionButton: {
    minHeight: 44,
    flex: 1,
    borderRadius: Radius.full,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryAction: { backgroundColor: Colors.actionPrimary },
  primaryActionText: {
    ...Typography.caption,
    color: Colors.onActionPrimary,
    fontWeight: '800',
  },
  secondaryAction: {
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surfaceElevated,
  },
  secondaryActionText: {
    ...Typography.caption,
    color: Colors.text,
    fontWeight: '800',
  },
});
