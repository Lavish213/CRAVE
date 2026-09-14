// src/components/PlaceVideoGallery.tsx
//
// Approved food videos for a place, plus the entry point into recording
// a new one. Self-contained (fetches its own feed) so place/[id].tsx only
// needs to render <PlaceVideoGallery placeId={place.id} /> once.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Modal, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Image } from 'expo-image';
import { useVideoPlayer, VideoView } from 'expo-video';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';

import { Colors, Radius, Spacing } from '../constants/colors';
import { FeedVideo, fetchVideoFeed } from '../api/videos';
import { useAuthStore } from '../stores/authStore';
import { useToast } from '../hooks/useToast';
import { requestAuthGate } from '../stores/authGateStore';
import { ReportVideoSheet } from './ReportVideoSheet';
import { useVideoQueueStore, QueuedVideo } from '../stores/videoQueueStore';

const THUMB_SIZE = 96;

// videoQueueStore is a per-device local queue, not synced across users --
// only the person who recorded a video ever has it in their own store, so
// these placeholders are naturally private to the uploader's own device
// even though this component itself is rendered for every viewer of the
// place. Deliberately excludes the terminal 'failed'/'rejected'/
// 'missing_local_file' states: those need a retry/delete decision, which
// already lives on the dedicated Uploads screen (app/uploads.tsx) -- this
// gallery only needs to answer "is one of my videos on its way in?".
const LOCAL_VIDEO_STATUS_COPY: Partial<Record<QueuedVideo['syncState'], string>> = {
  recorded: 'Queued',
  requesting_url: 'Uploading…',
  uploading: 'Uploading…',
  completing: 'Uploading…',
  reviewing: 'Under review',
};

function isLocalVideoPending(state: QueuedVideo['syncState']): boolean {
  return state in LOCAL_VIDEO_STATUS_COPY;
}

interface Props {
  placeId: string;
}

export function PlaceVideoGallery({ placeId }: Props) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const [videos, setVideos] = useState<FeedVideo[]>([]);
  const [playingVideo, setPlayingVideo] = useState<FeedVideo | null>(null);
  const queuedVideos = useVideoQueueStore((s) => s.videos);

  // Newest-first, same order recordVideo itself stores them in (see
  // videoQueueStore.ts's recordVideo: `[video, ...get().videos]`).
  const localPlaceholders = useMemo(
    () =>
      user
        ? queuedVideos.filter(
            (v) => v.placeId === placeId && v.uploadedBy === user.id && isLocalVideoPending(v.syncState)
          )
        : [],
    [queuedVideos, user, placeId]
  );

  // Confirmed CodeRabbit finding on PR #314: two separate call sites below
  // both fetch this same feed (initial mount/placeId-change, and a
  // placeholder-loss refetch) with no ordering guarantee between them --
  // navigating to a new place while a slower request for the previous one
  // is still in flight, or either request simply resolving out of order,
  // could let a stale response overwrite newer data. A monotonically
  // increasing request id shared by both call sites means a response is
  // only ever applied if it's still the most recent request issued,
  // regardless of which effect started it or how long it took.
  const latestRequestIdRef = useRef(0);
  const refetchFeed = useCallback((forPlaceId: string) => {
    const requestId = ++latestRequestIdRef.current;
    fetchVideoFeed({ placeId: forPlaceId, limit: 20 })
      .then((data) => {
        if (latestRequestIdRef.current !== requestId) return;
        setVideos(data.videos);
      })
      .catch((err: any) => {
        if (latestRequestIdRef.current !== requestId) return;
        if (__DEV__) console.warn('[PlaceVideoGallery] fetch_failed', err?.response?.status, err?.message);
      });
  }, []);

  useEffect(() => {
    refetchFeed(placeId);
  }, [placeId, refetchFeed]);

  // A locally-queued video for this place disappearing from
  // localPlaceholders (rather than just changing syncState) means it either
  // finished -- approved and pruned by videoQueueStore's own prune-on-
  // next-pass logic -- or was dismissed/deleted. Either way, the server
  // feed may now have a new video this component hasn't fetched yet, so
  // refetch instead of waiting for the user to leave and reopen this place.
  const prevPlaceholderIdsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    const prevIds = prevPlaceholderIdsRef.current;
    const currentIds = new Set(localPlaceholders.map((v) => v.id));
    const lostAny = Array.from(prevIds).some((id) => !currentIds.has(id));
    prevPlaceholderIdsRef.current = currentIds;
    if (lostAny) {
      refetchFeed(placeId);
    }
  }, [localPlaceholders, placeId, refetchFeed]);

  const handleRecordPress = useCallback(() => {
    if (!user) {
      requestAuthGate({
        actionType: 'record_place_video',
        reason: 'default',
        sourceRoute: `/place/${placeId}`,
        targetIds: [placeId],
        destination: `/record-video/${placeId}`,
        idempotent: true,
        // Intentionally deferred, not forgotten: one of the 4 lower-value
        // auth-gate call sites left as a no-op resume this pass (Save on
        // place/[id].tsx and Rank submission on rank/[placeId].tsx got the
        // real resume wiring) -- this only gates navigation intent, nothing
        // is captured here to replay.
        resume: () => undefined,
      });
      return;
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    router.push(`/record-video/${placeId}`);
  }, [user, placeId, router]);

  const handlePlaceholderPress = useCallback(() => {
    router.push('/uploads');
  }, [router]);

  if (videos.length === 0 && localPlaceholders.length === 0) {
    return (
      <View style={styles.container}>
        <TouchableOpacity style={styles.recordChip} onPress={handleRecordPress}>
          <Ionicons name="videocam" size={16} color={Colors.background} />
          <Text style={styles.recordChipText}>Record a video</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <TouchableOpacity style={styles.recordThumb} onPress={handleRecordPress}>
          <Ionicons name="videocam" size={22} color={Colors.text} />
          <Text style={styles.recordThumbText}>Record</Text>
        </TouchableOpacity>
        {localPlaceholders.map((v) => (
          <TouchableOpacity
            key={v.id}
            style={[styles.thumbWrap, styles.localPlaceholder]}
            onPress={handlePlaceholderPress}
            accessibilityRole="button"
            accessibilityLabel={`${LOCAL_VIDEO_STATUS_COPY[v.syncState]} — view in your uploads`}
          >
            <ActivityIndicator size="small" color={Colors.brand} />
            <Text style={styles.localPlaceholderText} numberOfLines={2}>
              {LOCAL_VIDEO_STATUS_COPY[v.syncState]}
            </Text>
          </TouchableOpacity>
        ))}
        {videos.map((v, index) => (
          <TouchableOpacity
            key={v.id}
            style={styles.thumbWrap}
            onPress={() => setPlayingVideo(v)}
            accessibilityRole="button"
            accessibilityLabel={`Play video ${index + 1} of ${videos.length}`}
          >
            {v.thumbnailUrl ? (
              <Image source={{ uri: v.thumbnailUrl }} style={styles.thumb} contentFit="cover" cachePolicy="disk" />
            ) : (
              <View style={[styles.thumb, styles.thumbPlaceholder]} />
            )}
            <View style={styles.playBadge}>
              <Ionicons name="play" size={14} color={Colors.text} />
            </View>
          </TouchableOpacity>
        ))}
      </View>

      <Modal visible={!!playingVideo} animationType="fade" onRequestClose={() => setPlayingVideo(null)}>
        {playingVideo && (
          <VideoPlaybackModal video={playingVideo} onClose={() => setPlayingVideo(null)} />
        )}
      </Modal>
    </View>
  );
}

function VideoPlaybackModal({ video, onClose }: { video: FeedVideo; onClose: () => void }) {
  const user = useAuthStore((s) => s.user);
  const toast = useToast((s) => s.show);
  const [reportVisible, setReportVisible] = useState(false);
  const player = useVideoPlayer(video.videoUrl ?? '', (p) => {
    p.loop = true;
    p.play();
  });

  const handleReportPress = () => {
    if (!user) {
      requestAuthGate({
        actionType: 'report_place_video',
        reason: 'default',
        sourceRoute: `/place/${video.placeId}`,
        targetIds: [video.id],
        idempotent: true,
        // Intentionally deferred, not forgotten: one of the 4 lower-value
        // auth-gate call sites left as a no-op resume this pass -- see
        // handleRecordPress's identical note above.
        resume: () => undefined,
      });
      return;
    }
    setReportVisible(true);
  };

  return (
    <View style={styles.playbackContainer}>
      <VideoView player={player} style={StyleSheet.absoluteFill} contentFit="contain" />
      <TouchableOpacity
        style={styles.playbackClose}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Close video"
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name="close" size={28} color={Colors.text} />
      </TouchableOpacity>
      <TouchableOpacity
        style={styles.playbackReport}
        onPress={handleReportPress}
        accessibilityRole="button"
        accessibilityLabel="Report this video"
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name="flag-outline" size={22} color={Colors.text} />
      </TouchableOpacity>
      <ReportVideoSheet
        visible={reportVisible}
        videoId={video.id}
        onClose={() => setReportVisible(false)}
        onReported={() => toast('Thanks — we’ll take a look.')}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: Spacing.md,
  },
  row: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.lg,
    gap: Spacing.sm,
  },
  recordChip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    marginHorizontal: Spacing.lg,
    backgroundColor: Colors.actionPrimary,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderRadius: Radius.pill,
    gap: Spacing.xs,
  },
  recordChipText: {
    color: Colors.onActionPrimary,
    fontWeight: '700',
    fontSize: 14,
  },
  recordThumb: {
    width: THUMB_SIZE,
    height: THUMB_SIZE,
    borderRadius: Radius.md,
    backgroundColor: Colors.surfaceElevated,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.sm,
  },
  recordThumbText: {
    color: Colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
    marginTop: Spacing.xs,
  },
  thumbWrap: {
    width: THUMB_SIZE,
    height: THUMB_SIZE,
    borderRadius: Radius.md,
    overflow: 'hidden',
    marginRight: Spacing.sm,
  },
  thumb: {
    width: '100%',
    height: '100%',
  },
  thumbPlaceholder: {
    backgroundColor: Colors.surfaceElevated,
  },
  localPlaceholder: {
    backgroundColor: Colors.surfaceElevated,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xs,
    gap: Spacing.xs,
  },
  localPlaceholderText: {
    color: Colors.textSecondary,
    fontSize: 10,
    fontWeight: '600',
    textAlign: 'center',
  },
  playBadge: {
    position: 'absolute',
    bottom: Spacing.xs,
    right: Spacing.xs,
    width: 24,
    height: 24,
    borderRadius: Radius.full,
    backgroundColor: 'rgba(0,0,0,0.55)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  playbackContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  playbackClose: {
    position: 'absolute',
    top: Spacing.xxl,
    left: Spacing.lg,
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  playbackReport: {
    position: 'absolute',
    top: Spacing.xxl,
    right: Spacing.lg,
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
