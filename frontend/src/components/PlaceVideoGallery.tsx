// src/components/PlaceVideoGallery.tsx
//
// Approved food videos for a place, plus the entry point into recording
// a new one. Self-contained (fetches its own feed) so place/[id].tsx only
// needs to render <PlaceVideoGallery placeId={place.id} /> once.
import React, { useCallback, useEffect, useState } from 'react';
import { Modal, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Image } from 'expo-image';
import { useVideoPlayer, VideoView } from 'expo-video';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';

import { Colors, Radius, Spacing } from '../constants/colors';
import { FeedVideo, fetchVideoFeed } from '../api/videos';
import { useAuthStore } from '../stores/authStore';
import { useToast } from '../hooks/useToast';

const THUMB_SIZE = 96;

interface Props {
  placeId: string;
}

export function PlaceVideoGallery({ placeId }: Props) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const toast = useToast((s) => s.show);
  const [videos, setVideos] = useState<FeedVideo[]>([]);
  const [playingVideo, setPlayingVideo] = useState<FeedVideo | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchVideoFeed({ placeId, limit: 20 })
      .then((data) => {
        if (!cancelled) setVideos(data.videos);
      })
      .catch((err: any) => {
        if (__DEV__) console.warn('[PlaceVideoGallery] fetch_failed', err?.response?.status, err?.message);
      });
    return () => {
      cancelled = true;
    };
  }, [placeId]);

  const handleRecordPress = useCallback(() => {
    if (!user) {
      toast('Sign in to record a food video');
      return;
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    router.push(`/record-video/${placeId}`);
  }, [user, placeId, router, toast]);

  if (videos.length === 0) {
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
        {videos.map((v) => (
          <TouchableOpacity key={v.id} style={styles.thumbWrap} onPress={() => setPlayingVideo(v)}>
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
  const player = useVideoPlayer(video.videoUrl ?? '', (p) => {
    p.loop = true;
    p.play();
  });

  return (
    <View style={styles.playbackContainer}>
      <VideoView player={player} style={StyleSheet.absoluteFill} contentFit="contain" />
      <TouchableOpacity style={styles.playbackClose} onPress={onClose}>
        <Ionicons name="close" size={28} color={Colors.text} />
      </TouchableOpacity>
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
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderRadius: Radius.pill,
    gap: Spacing.xs,
  },
  recordChipText: {
    color: Colors.background,
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
});
