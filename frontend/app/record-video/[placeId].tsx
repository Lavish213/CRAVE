// app/record-video/[placeId].tsx
//
// Record a short food video for a place. Records locally first and
// queues it via videoQueueStore -- the network is never in the critical
// path of "did my recording save" (see docs on the offline record/sync
// design in videoQueueStore.ts). Compression/food-scoring/approval all
// happen out-of-process on the backend afterward.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { CameraView, useCameraPermissions, useMicrophonePermissions } from 'expo-camera';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Colors, Radius, Spacing } from '../../src/constants/colors';
import { BeatCueOverlay } from '../../src/components/BeatCueOverlay';
import { VideoTemplateStrip } from '../../src/components/VideoTemplateStrip';
import { useVideoTemplates } from '../../src/hooks/useVideoTemplates';
import { useVideoQueueStore } from '../../src/stores/videoQueueStore';
import { useAuthStore } from '../../src/stores/authStore';
import { useToast } from '../../src/hooks/useToast';
import type { VideoContentType } from '../../src/api/videos';

const MAX_DURATION_SEC = 10; // matches backend settings.video_max_duration_ms default

function contentTypeForUri(uri: string): VideoContentType {
  const ext = uri.split('.').pop()?.toLowerCase();
  if (ext === 'mov') return 'video/quicktime';
  if (ext === 'webm') return 'video/webm';
  return 'video/mp4';
}

export default function RecordVideoScreen() {
  const { placeId } = useLocalSearchParams<{ placeId: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const user = useAuthStore((s) => s.user);
  const toast = useToast((s) => s.show);
  const recordVideo = useVideoQueueStore((s) => s.recordVideo);
  const runSyncPass = useVideoQueueStore((s) => s.runSyncPass);

  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const [micPermission, requestMicPermission] = useMicrophonePermissions();
  const { templates } = useVideoTemplates();

  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [saving, setSaving] = useState(false);

  const cameraRef = useRef<CameraView>(null);
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recordingStartRef = useRef(0);

  useEffect(() => {
    return () => {
      if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current);
    };
  }, []);

  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId) ?? null;

  const startRecording = useCallback(async () => {
    if (!cameraRef.current || isRecording) return;
    // Verify identity and target *before* activating the camera at all --
    // previously this screen recorded a full video first and only
    // checked placeId/user afterward, silently discarding a completed
    // recording with zero feedback if either was missing. The render-time
    // guards below already keep a signed-out viewer from reaching this
    // screen through its own normal entry point, but this button is the
    // one that actually spends the user's effort (a real recording), so
    // it re-verifies rather than trusting that guard alone.
    if (!placeId || !user?.id) {
      toast("Couldn't save your video — sign in and try again.");
      return;
    }
    setIsRecording(true);
    recordingStartRef.current = Date.now();
    setElapsedMs(0);
    elapsedTimerRef.current = setInterval(() => {
      setElapsedMs(Date.now() - recordingStartRef.current);
    }, 100);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    try {
      const result = await cameraRef.current.recordAsync({ maxDuration: MAX_DURATION_SEC });
      if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current);
      setIsRecording(false);

      if (!result?.uri) return; // recording was cancelled with no output

      // Re-checked against the *current* auth state, not the `user`
      // this closure captured when startRecording began -- a sign-out
      // during the recording itself (rare, but real: this can take up
      // to MAX_DURATION_SEC) would otherwise go undetected, since the
      // closed-over `user` variable still holds the pre-sign-out
      // identity for this call's entire remaining lifetime regardless
      // of what the store holds by the time it actually checks. That
      // let a video queue and sync under a session that had already
      // ended. Also requires it's still the *same* user (not just "a"
      // user), in case someone signed in as a different account in the
      // gap.
      const currentUser = useAuthStore.getState().user;
      if (!placeId || !currentUser?.id || currentUser.id !== user?.id) {
        toast("Couldn't save your video — you're no longer signed in.");
        return;
      }

      setSaving(true);
      try {
        await recordVideo({
          sourceUri: result.uri,
          placeId,
          contentType: contentTypeForUri(result.uri),
          uploadedBy: currentUser.id,
          templateId: selectedTemplateId,
        });
        toast("Saved — it'll post as soon as you're online.");
        runSyncPass(currentUser.id).catch(() => {});
        router.back();
      } catch (err: any) {
        toast(err?.message ?? "Couldn't save your video. Try again.");
      } finally {
        setSaving(false);
      }
    } catch (err) {
      if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current);
      setIsRecording(false);
      if (__DEV__) console.warn('[RecordVideoScreen] recordAsync_failed', err);
    }
  }, [isRecording, placeId, user?.id, selectedTemplateId, recordVideo, runSyncPass, router, toast]);

  const stopRecording = useCallback(() => {
    cameraRef.current?.stopRecording();
  }, []);

  // Preconditions, verified before the camera is ever mounted -- this
  // screen's one known entry point (PlaceVideoGallery) already gates on
  // sign-in before navigating here, but that guard lives in the caller,
  // not this route; a deep link or any future entry point would otherwise
  // reach a fully-functional camera UI with no identity/target to record
  // against at all.
  if (!placeId) {
    return (
      <View style={[styles.container, styles.centered]}>
        <Ionicons name="alert-circle-outline" size={48} color={Colors.textSecondary} />
        <Text style={styles.permissionText}>This video link is invalid.</Text>
        <TouchableOpacity style={styles.permissionButton} onPress={() => router.back()}>
          <Text style={styles.permissionButtonText}>Go back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!user) {
    return (
      <View style={[styles.container, styles.centered]}>
        <Ionicons name="person-circle-outline" size={48} color={Colors.textSecondary} />
        <Text style={styles.permissionText}>Sign in to record a food video.</Text>
        <TouchableOpacity style={styles.permissionButton} onPress={() => router.back()}>
          <Text style={styles.permissionButtonText}>Go back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!cameraPermission || !micPermission) {
    return <View style={styles.container} />;
  }

  if (!cameraPermission.granted || !micPermission.granted) {
    // canAskAgain is false once the OS has permanently denied the prompt
    // (or the user picked "Don't ask again") -- requesting again in that
    // state just silently no-ops, so "Allow Access" would sit there
    // looking actionable while doing nothing. Route to the OS Settings
    // app instead, matching this app's own existing convention (see
    // settings.tsx's identical handling for notification permissions).
    const blocked = !cameraPermission.canAskAgain || !micPermission.canAskAgain;
    return (
      <View style={[styles.container, styles.centered]}>
        <Ionicons name="videocam-outline" size={48} color={Colors.textSecondary} />
        <Text style={styles.permissionText}>
          {blocked
            ? 'Camera and microphone access is blocked. Enable it in Settings to record a food video.'
            : 'CRAVE needs camera and microphone access to record a food video.'}
        </Text>
        <TouchableOpacity
          style={styles.permissionButton}
          onPress={async () => {
            if (blocked) {
              Linking.openSettings().catch(() => toast("Couldn't open Settings."));
              return;
            }
            await requestCameraPermission();
            await requestMicPermission();
          }}
        >
          <Text style={styles.permissionButtonText}>{blocked ? 'Open Settings' : 'Allow Access'}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} mode="video" facing="back" />

      <TouchableOpacity
        style={[styles.closeButton, { top: insets.top + Spacing.md }]}
        onPress={() => router.back()}
        accessibilityRole="button"
        accessibilityLabel="Close"
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name="close" size={28} color={Colors.text} />
      </TouchableOpacity>

      {isRecording && <BeatCueOverlay template={selectedTemplate} elapsedMs={elapsedMs} />}

      {!isRecording && (
        <View style={[styles.templateStripWrap, { bottom: 140 + insets.bottom }]}>
          <VideoTemplateStrip
            templates={templates}
            selectedId={selectedTemplateId}
            onSelect={setSelectedTemplateId}
          />
        </View>
      )}

      <View style={[styles.controls, { bottom: Spacing.xxl + insets.bottom }]}>
        {isRecording && (
          <Text style={styles.timer}>
            {Math.min(elapsedMs / 1000, MAX_DURATION_SEC).toFixed(1)}s / {MAX_DURATION_SEC}s
          </Text>
        )}
        <TouchableOpacity
          style={[styles.recordButton, isRecording && styles.recordButtonActive]}
          onPress={isRecording ? stopRecording : startRecording}
          disabled={saving}
          accessibilityRole="button"
          accessibilityLabel={isRecording ? 'Stop recording' : 'Start recording'}
        >
          {saving ? (
            <ActivityIndicator color={Colors.text} />
          ) : (
            <View style={[styles.recordButtonInner, isRecording && styles.recordButtonInnerActive]} />
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  centered: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.xxl,
  },
  permissionText: {
    color: Colors.textSecondary,
    fontSize: 15,
    textAlign: 'center',
    marginTop: Spacing.lg,
    marginBottom: Spacing.xl,
  },
  permissionButton: {
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.md,
    borderRadius: Radius.pill,
  },
  permissionButtonText: {
    color: Colors.background,
    fontWeight: '700',
    fontSize: 15,
  },
  closeButton: {
    position: 'absolute',
    left: Spacing.lg,
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
  },
  templateStripWrap: {
    position: 'absolute',
    left: 0,
    right: 0,
  },
  controls: {
    position: 'absolute',
    left: 0,
    right: 0,
    alignItems: 'center',
  },
  timer: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '600',
    marginBottom: Spacing.md,
  },
  recordButton: {
    width: 76,
    height: 76,
    borderRadius: Radius.full,
    borderWidth: 4,
    borderColor: Colors.text,
    alignItems: 'center',
    justifyContent: 'center',
  },
  recordButtonActive: {
    borderColor: Colors.error,
  },
  recordButtonInner: {
    width: 60,
    height: 60,
    borderRadius: Radius.full,
    backgroundColor: Colors.error,
  },
  recordButtonInnerActive: {
    width: 28,
    height: 28,
    borderRadius: Radius.sm,
  },
});
