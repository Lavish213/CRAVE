// app/add-spot.tsx
//
// GPS-based "find and add a new spot" flow. Gets a fresh, high-accuracy
// location fix (not the cached session-level one from useLocation — the
// user may have moved since app launch, and precision matters here since
// we're matching against a 150m search radius), searches nearby, and lets
// the user open an existing CRAVE place or submit a new candidate signal.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import * as Location from 'expo-location';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { Colors, Spacing, Radius } from '../src/constants/colors';
import { useToast } from '../src/hooks/useToast';
import { useAuthStore } from '../src/stores/authStore';
import { AuthSheet } from '../src/components/AuthSheet';
import { NearbyCandidate, confirmNewSpot, searchNearby } from '../src/api/nearby';
import { useUploadImage } from '../src/hooks/useUploadImage';
import { useVideoQueueStore } from '../src/stores/videoQueueStore';
import type { VideoContentType } from '../src/api/videos';

type LoadState =
  | 'locating'
  | 'searching'
  | 'ready'
  | 'denied'
  | 'blocked'
  | 'error'
  | 'unauthenticated';

// Mirrors record-video/[placeId].tsx's identical helper -- kept local since
// that screen is otherwise unrelated to this one and this is the only other
// call site.
function contentTypeForUri(uri: string): VideoContentType {
  const ext = uri.split('.').pop()?.toLowerCase();
  if (ext === 'mov') return 'video/quicktime';
  if (ext === 'webm') return 'video/webm';
  return 'video/mp4';
}

export default function AddSpotScreen() {
  const router = useRouter();
  const toast = useToast((s) => s.show);
  const user = useAuthStore((s) => s.user);
  const authLoading = useAuthStore((s) => s.loading);
  const { upload } = useUploadImage();
  const recordVideo = useVideoQueueStore((s) => s.recordVideo);

  const [state, setState] = useState<LoadState>('locating');
  const [results, setResults] = useState<NearbyCandidate[]>([]);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [confirmedIds, setConfirmedIds] = useState<Set<string>>(new Set());
  const [authVisible, setAuthVisible] = useState(false);

  // Carried over from food-evidence.tsx's "Continue" button -- a photo or
  // video captured there, waiting for whichever place the user identifies
  // here. Undefined/invalid params (any entry into this screen that isn't
  // via that button) simply means there's nothing pending, not an error.
  const { mediaUri, mediaKind, mediaFileSize, mediaMimeType } = useLocalSearchParams<{
    mediaUri?: string;
    mediaKind?: string;
    mediaFileSize?: string;
    mediaMimeType?: string;
  }>();
  const pendingMedia = useMemo(() => {
    if (!mediaUri || (mediaKind !== 'photo' && mediaKind !== 'video')) return null;
    return {
      uri: mediaUri,
      kind: mediaKind as 'photo' | 'video',
      fileSize: mediaFileSize ? Number(mediaFileSize) : undefined,
      mimeType: mediaMimeType || undefined,
    };
  }, [mediaUri, mediaKind, mediaFileSize, mediaMimeType]);
  // Single-use per screen visit -- once the user has acted on one candidate
  // (attached, or explicitly deferred on a new-candidate signal), a second,
  // unrelated candidate tapped afterward must not silently inherit the same
  // media. 'idle' is the only state that still offers to attach it.
  const [mediaOutcome, setMediaOutcome] = useState<'idle' | 'uploading' | 'attached' | 'failed' | 'deferred'>('idle');

  const attachPendingMedia = useCallback(
    async (placeId: string) => {
      if (!pendingMedia) return;
      setMediaOutcome('uploading');
      try {
        if (pendingMedia.kind === 'photo') {
          if (!pendingMedia.fileSize) {
            throw new Error("Couldn't read your photo's file size");
          }
          await upload(
            { uri: pendingMedia.uri, fileSize: pendingMedia.fileSize, mimeType: pendingMedia.mimeType },
            placeId,
            'food',
          );
          toast('Photo submitted for this place');
        } else {
          if (!user?.id) throw new Error('Sign in to add a video');
          await recordVideo({
            sourceUri: pendingMedia.uri,
            placeId,
            contentType: contentTypeForUri(pendingMedia.uri),
            uploadedBy: user.id,
            templateId: null,
          });
          toast("Saved — it'll post as soon as you're online.");
        }
        setMediaOutcome('attached');
      } catch (err) {
        setMediaOutcome('failed');
        toast(err instanceof Error ? err.message : "Couldn't attach your media to this place");
      }
    },
    [pendingMedia, upload, recordVideo, user?.id, toast],
  );

  const runIdRef = useRef(0);

  const run = useCallback(async () => {
    const myRunId = ++runIdRef.current;

    if (authLoading) {
      setState('locating');
      return;
    }

    if (!user) {
      setState('unauthenticated');
      return;
    }

    setState('locating');
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (myRunId !== runIdRef.current) return;
      if (permission.status !== 'granted') {
        setState(permission.canAskAgain === false ? 'blocked' : 'denied');
        return;
      }

      const pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });
      if (myRunId !== runIdRef.current) return;

      setState('searching');
      const found = await searchNearby(pos.coords.latitude, pos.coords.longitude);
      if (myRunId !== runIdRef.current) return;
      setResults(found);
      setState('ready');
    } catch (err) {
      if (myRunId !== runIdRef.current) return;
      if (__DEV__) console.error('[ADD_SPOT ERROR]', err);
      setState('error');
    }
  }, [user, authLoading]);

  useEffect(() => {
    void run();
  }, [run]);

  const accountGenerationRef = useRef(0);
  useEffect(() => {
    accountGenerationRef.current += 1;
    setConfirmedIds(new Set());
    setConfirmingId(null);
  }, [user?.id]);

  const handleConfirm = async (candidate: NearbyCandidate) => {
    if (!user) {
      toast('Sign in to add a new spot');
      return;
    }
    const submittingGeneration = accountGenerationRef.current;
    const key = candidate.external_id ?? candidate.name;
    setConfirmingId(key);
    try {
      void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      await confirmNewSpot({
        external_id: candidate.external_id,
        name: candidate.name,
        lat: candidate.lat,
        lng: candidate.lng,
        address: candidate.address,
        category_hint: candidate.category_hint,
      });
      if (submittingGeneration !== accountGenerationRef.current) return;
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setConfirmedIds((prev) => new Set(prev).add(key));
      // A brand-new candidate has no place_id yet -- confirmNewSpot() only
      // returns a candidate_id, since this creates a DiscoveryCandidate for
      // the normal async promotion pipeline, not a Place row. There's
      // nowhere to attach pending media yet on this branch, so say so
      // explicitly instead of silently dropping it (the media stays
      // captured on food-evidence.tsx's side only in the sense that this
      // screen simply doesn't touch it here -- there's no "come back and
      // retry" mechanism beyond the user redoing food-evidence, which this
      // copy is honest about).
      if (pendingMedia && mediaOutcome === 'idle') {
        setMediaOutcome('deferred');
        toast(
          `Got it — added as a signal. It'll appear once confirmed by more activity. Come back once it's live to add your ${pendingMedia.kind}.`,
        );
      } else {
        toast("Got it — added as a signal. It'll appear once confirmed by more activity.");
      }
    } catch (err) {
      if (submittingGeneration !== accountGenerationRef.current) return;
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      toast(err instanceof Error ? err.message : 'Could not submit this spot');
    }
    if (submittingGeneration === accountGenerationRef.current) {
      setConfirmingId(null);
    }
  };

  if (state === 'locating' || state === 'searching') {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.statusText}>
          {state === 'locating' ? 'Finding your location…' : 'Searching nearby…'}
        </Text>
      </View>
    );
  }

  if (state === 'denied' || state === 'blocked') {
    const blocked = state === 'blocked';
    return (
      <View style={styles.centered}>
        <Ionicons name="location-outline" size={32} color={Colors.textSecondary} />
        <Text style={styles.statusText}>
          {blocked
            ? 'Location access is turned off for CRAVE. Enable it in Settings to find spots near you.'
            : 'Location access is needed to find spots near you.'}
        </Text>
        <TouchableOpacity
          style={styles.retryBtn}
          onPress={() => {
            if (blocked) {
              void Linking.openSettings();
            } else {
              void run();
            }
          }}
          accessibilityRole="button"
          accessibilityLabel={blocked ? 'Open Settings' : 'Try location permission again'}
        >
          <Text style={styles.retryLabel}>{blocked ? 'Open Settings' : 'Try again'}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (state === 'unauthenticated') {
    return (
      <View style={styles.centered}>
        <Ionicons name="person-circle-outline" size={32} color={Colors.textSecondary} />
        <Text style={styles.statusText}>Sign in to add a new spot.</Text>
        <TouchableOpacity
          style={styles.retryBtn}
          onPress={() => setAuthVisible(true)}
          accessibilityRole="button"
          accessibilityLabel="Sign in"
        >
          <Text style={styles.retryLabel}>Sign in</Text>
        </TouchableOpacity>
        <AuthSheet visible={authVisible} onClose={() => setAuthVisible(false)} reason="add-spot" />
      </View>
    );
  }

  if (state === 'error') {
    return (
      <View style={styles.centered}>
        <Ionicons name="alert-circle-outline" size={32} color={Colors.textSecondary} />
        <Text style={styles.statusText}>Couldn't search nearby spots.</Text>
        <TouchableOpacity
          style={styles.retryBtn}
          onPress={() => void run()}
          accessibilityRole="button"
          accessibilityLabel="Retry nearby search"
        >
          <Text style={styles.retryLabel}>Try again</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>What's around you</Text>
      <Text style={styles.subtitle}>
        Tap the spot you're at. Already-listed places open directly; new ones
        get submitted as a signal toward being added.
      </Text>

      {pendingMedia && mediaOutcome === 'idle' ? (
        <View style={styles.mediaBanner}>
          <Ionicons
            name={pendingMedia.kind === 'photo' ? 'image-outline' : 'videocam-outline'}
            size={18}
            color={Colors.primary}
          />
          <Text style={styles.mediaBannerText}>
            {pendingMedia.kind === 'photo' ? 'Photo' : 'Video'} ready — tap a place below to attach it.
          </Text>
        </View>
      ) : null}

      {results.length === 0 ? (
        <Text style={styles.empty}>Nothing found within range. Try again once you're closer.</Text>
      ) : (
        results.map((candidate) => {
          const key = candidate.external_id ?? candidate.name;
          const isConfirming = confirmingId === key;
          const isConfirmed = confirmedIds.has(key);

          return (
            <View key={key} style={styles.card}>
              <View style={styles.cardBody}>
                <Text style={styles.cardName}>{candidate.name}</Text>
                {candidate.address ? <Text style={styles.cardAddress}>{candidate.address}</Text> : null}
                <Text style={styles.cardDistance}>{Math.round(candidate.distance_m)}m away</Text>
              </View>

              {candidate.already_in_crave ? (
                <TouchableOpacity
                  style={styles.actionBtn}
                  onPress={() => {
                    // Fire-and-forget: uploading shouldn't block getting to
                    // the place, and toast() renders from a root-mounted
                    // container so its outcome still surfaces after
                    // navigating away. Guarded on 'idle' so a second,
                    // different candidate tapped afterward doesn't also
                    // try to claim the same media.
                    if (pendingMedia && mediaOutcome === 'idle' && candidate.place_id) {
                      void attachPendingMedia(candidate.place_id);
                    }
                    router.push(`/place/${candidate.place_id}`);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`Open ${candidate.name}`}
                >
                  <Text style={styles.actionLabel}>Open</Text>
                  <Ionicons name="arrow-forward" size={16} color={Colors.primary} />
                </TouchableOpacity>
              ) : (
                <TouchableOpacity
                  style={[styles.actionBtn, isConfirmed && styles.actionBtnDone]}
                  onPress={() => void handleConfirm(candidate)}
                  disabled={isConfirming || isConfirmed}
                  accessibilityRole="button"
                  accessibilityLabel={`Confirm this is ${candidate.name}`}
                >
                  {isConfirming ? (
                    <ActivityIndicator size="small" color={Colors.text} />
                  ) : (
                    <Text style={[styles.actionLabel, isConfirmed && styles.actionLabelDone]}>
                      {isConfirmed ? 'Submitted' : 'This is it'}
                    </Text>
                  )}
                </TouchableOpacity>
              )}
            </View>
          );
        })
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.lg, paddingBottom: 48 },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xl,
    gap: Spacing.md,
    backgroundColor: Colors.background,
  },
  statusText: { color: Colors.textSecondary, fontSize: 14, textAlign: 'center' },
  mediaBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    padding: Spacing.md,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.primary,
    backgroundColor: Colors.surface,
    marginBottom: Spacing.lg,
  },
  mediaBannerText: { flex: 1, color: Colors.text, fontSize: 13, fontWeight: '600' },
  retryBtn: {
    marginTop: Spacing.sm,
    paddingHorizontal: 18,
    paddingVertical: 12,
    minHeight: 44,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  retryLabel: { color: Colors.text, fontWeight: '600', fontSize: 14 },
  title: { fontSize: 22, fontWeight: '800', color: Colors.text, marginBottom: 6 },
  subtitle: { fontSize: 13, color: Colors.textSecondary, marginBottom: Spacing.lg, lineHeight: 18 },
  empty: { color: Colors.textSecondary, fontSize: 14, paddingVertical: Spacing.lg, textAlign: 'center' },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    padding: Spacing.md,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    marginBottom: Spacing.sm,
  },
  cardBody: { flex: 1, gap: 2 },
  cardName: { fontSize: 15, fontWeight: '700', color: Colors.text },
  cardAddress: { fontSize: 12, color: Colors.textSecondary },
  cardDistance: { fontSize: 11, color: Colors.textSecondary, marginTop: 2 },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: Colors.border,
    minHeight: 44,
  },
  actionBtnDone: { borderColor: Colors.border, opacity: 0.6 },
  actionLabel: { fontSize: 13, fontWeight: '700', color: Colors.text },
  actionLabelDone: { color: Colors.textSecondary },
});
