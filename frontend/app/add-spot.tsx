import React, { useCallback, useEffect, useRef, useState } from 'react';
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

import { Colors, Radius, Spacing } from '../src/constants/colors';
import { useToast } from '../src/hooks/useToast';
import { useAuthStore } from '../src/stores/authStore';
import { AuthSheet } from '../src/components/AuthSheet';
import { NearbyCandidate, confirmNewSpot, searchNearby } from '../src/api/nearby';
import { usePostingDraftStore } from '../src/stores/postingDraftStore';

type LoadState = 'locating' | 'searching' | 'ready' | 'denied' | 'blocked' | 'error' | 'unauthenticated';

export default function AddSpotScreen() {
  const router = useRouter();
  const toast = useToast((state) => state.show);
  const user = useAuthStore((state) => state.user);
  const authLoading = useAuthStore((state) => state.loading);
  const { draftId } = useLocalSearchParams<{ draftId?: string }>();

  const draft = usePostingDraftStore((state) =>
    draftId ? state.drafts.find((item) => item.id === draftId) : undefined,
  );
  const setDraftPlace = usePostingDraftStore((state) => state.setDraftPlace);
  const setDraftCandidate = usePostingDraftStore((state) => state.setDraftCandidate);

  const [state, setState] = useState<LoadState>('locating');
  const [results, setResults] = useState<NearbyCandidate[]>([]);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [confirmedIds, setConfirmedIds] = useState<Set<string>>(new Set());
  const [authVisible, setAuthVisible] = useState(false);
  const runIdRef = useRef(0);
  const accountGenerationRef = useRef(0);

  const returnToComposer = useCallback(() => {
    if (draftId) {
      router.replace({ pathname: '/food-evidence', params: { draftId } });
    } else {
      router.back();
    }
  }, [draftId, router]);

  const run = useCallback(async () => {
    const runId = ++runIdRef.current;
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
      if (runId !== runIdRef.current) return;
      if (permission.status !== 'granted') {
        setState(permission.canAskAgain === false ? 'blocked' : 'denied');
        return;
      }

      const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      if (runId !== runIdRef.current) return;
      setState('searching');
      const found = await searchNearby(position.coords.latitude, position.coords.longitude);
      if (runId !== runIdRef.current) return;
      setResults(found);
      setState('ready');
    } catch (error) {
      if (runId !== runIdRef.current) return;
      if (__DEV__) console.error('[ADD_SPOT ERROR]', error);
      setState('error');
    }
  }, [authLoading, user]);

  useEffect(() => {
    void run();
  }, [run]);

  useEffect(() => {
    accountGenerationRef.current += 1;
    setConfirmedIds(new Set());
    setConfirmingId(null);
  }, [user?.id]);

  async function handleConfirm(candidate: NearbyCandidate) {
    if (!user) {
      toast('Sign in to add a new spot');
      return;
    }
    const generation = accountGenerationRef.current;
    const key = candidate.external_id ?? candidate.name;
    setConfirmingId(key);
    try {
      void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      const result = await confirmNewSpot({
        external_id: candidate.external_id,
        name: candidate.name,
        lat: candidate.lat,
        lng: candidate.lng,
        address: candidate.address,
        category_hint: candidate.category_hint,
      });
      if (generation !== accountGenerationRef.current) return;
      setConfirmedIds((previous) => new Set(previous).add(key));
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);

      if (draft) {
        setDraftCandidate(draft.id, result.candidate_id, candidate.name);
        toast("Restaurant submitted. Your draft is safe while we're verifying it.");
        returnToComposer();
      } else {
        toast("Got it — added as a signal. It'll appear once confirmed by more activity.");
      }
    } catch (error) {
      if (generation !== accountGenerationRef.current) return;
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      toast(error instanceof Error ? error.message : 'Could not submit this spot');
    } finally {
      if (generation === accountGenerationRef.current) setConfirmingId(null);
    }
  }

  if (state === 'locating' || state === 'searching') {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.statusText}>{state === 'locating' ? 'Finding nearby places…' : 'Searching nearby…'}</Text>
      </View>
    );
  }

  if (state === 'denied' || state === 'blocked') {
    const blocked = state === 'blocked';
    return (
      <View style={styles.centered}>
        <Ionicons name="location-outline" size={34} color={Colors.textSecondary} />
        <Text style={styles.title}>{draft ? 'Location is optional' : 'Location unavailable'}</Text>
        <Text style={styles.statusText}>
          {draft
            ? 'CRAVE uses foreground location only to suggest nearby missing places. Your draft is safe; return and search restaurants by name instead.'
            : blocked
              ? 'Enable location in Settings to find nearby missing places.'
              : 'Location helps CRAVE find nearby missing places.'}
        </Text>
        {draft ? (
          <TouchableOpacity style={styles.primaryBtn} onPress={returnToComposer} accessibilityRole="button">
            <Text style={styles.primaryLabel}>Search restaurants instead</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={styles.retryBtn}
            onPress={() => blocked ? void Linking.openSettings() : void run()}
            accessibilityRole="button"
          >
            <Text style={styles.retryLabel}>{blocked ? 'Open Settings' : 'Try again'}</Text>
          </TouchableOpacity>
        )}
      </View>
    );
  }

  if (state === 'unauthenticated') {
    return (
      <View style={styles.centered}>
        <Ionicons name="person-circle-outline" size={34} color={Colors.textSecondary} />
        <Text style={styles.statusText}>Sign in to add a missing restaurant.</Text>
        <TouchableOpacity style={styles.primaryBtn} onPress={() => setAuthVisible(true)} accessibilityRole="button">
          <Text style={styles.primaryLabel}>Sign in</Text>
        </TouchableOpacity>
        <AuthSheet visible={authVisible} onClose={() => setAuthVisible(false)} reason="add-spot" />
      </View>
    );
  }

  if (state === 'error') {
    return (
      <View style={styles.centered}>
        <Ionicons name="alert-circle-outline" size={34} color={Colors.textSecondary} />
        <Text style={styles.statusText}>Couldn't search nearby places.</Text>
        {draft ? (
          <TouchableOpacity style={styles.primaryBtn} onPress={returnToComposer} accessibilityRole="button">
            <Text style={styles.primaryLabel}>Return to draft</Text>
          </TouchableOpacity>
        ) : null}
        <TouchableOpacity style={styles.retryBtn} onPress={() => void run()} accessibilityRole="button">
          <Text style={styles.retryLabel}>Try again</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>{draft ? 'IDENTIFY RESTAURANT' : 'ADD A SPOT'}</Text>
      <Text style={styles.title}>{draft ? 'Is it one of these?' : "What's around you"}</Text>
      <Text style={styles.subtitle}>
        {draft
          ? 'Selecting a place only identifies this draft. Nothing uploads or publishes until you finish the composer.'
          : 'Already-listed places open directly. New ones become verification signals.'}
      </Text>

      {draft ? (
        <View style={styles.mediaBanner}>
          <Ionicons name={draft.kind === 'video' ? 'videocam-outline' : draft.kind === 'photo' ? 'image-outline' : 'document-text-outline'} size={18} color={Colors.primary} />
          <Text style={styles.mediaBannerText}>Draft saved · no recapture required</Text>
        </View>
      ) : null}

      {results.length === 0 ? (
        <View style={styles.emptyBlock}>
          <Text style={styles.empty}>Nothing nearby matched.</Text>
          {draft ? (
            <TouchableOpacity style={styles.retryBtn} onPress={returnToComposer} accessibilityRole="button">
              <Text style={styles.retryLabel}>Search by name instead</Text>
            </TouchableOpacity>
          ) : null}
        </View>
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

              {candidate.already_in_crave && candidate.place_id ? (
                <TouchableOpacity
                  style={styles.actionBtn}
                  onPress={() => {
                    if (draft) {
                      setDraftPlace(draft.id, candidate.place_id!, candidate.name);
                      toast(`${candidate.name} selected`);
                      returnToComposer();
                    } else {
                      router.push(`/place/${candidate.place_id}`);
                    }
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={draft ? `Select ${candidate.name}` : `Open ${candidate.name}`}
                >
                  <Text style={styles.actionLabel}>{draft ? 'Select' : 'Open'}</Text>
                  <Ionicons name="arrow-forward" size={16} color={Colors.primary} />
                </TouchableOpacity>
              ) : (
                <TouchableOpacity
                  style={[styles.actionBtn, isConfirmed && styles.actionBtnDone]}
                  onPress={() => void handleConfirm(candidate)}
                  disabled={isConfirming || isConfirmed}
                  accessibilityRole="button"
                  accessibilityLabel={`Submit ${candidate.name} for verification`}
                >
                  {isConfirming ? (
                    <ActivityIndicator size="small" color={Colors.text} />
                  ) : (
                    <Text style={[styles.actionLabel, isConfirmed && styles.actionLabelDone]}>{isConfirmed ? 'Submitted' : 'This is it'}</Text>
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
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.xl, gap: Spacing.md, backgroundColor: Colors.background },
  eyebrow: { color: Colors.primary, fontSize: 11, fontWeight: '800', letterSpacing: 1.1, marginBottom: 6 },
  title: { fontSize: 24, fontWeight: '800', color: Colors.text, textAlign: 'center', marginBottom: 8 },
  statusText: { color: Colors.textSecondary, fontSize: 14, textAlign: 'center', lineHeight: 20 },
  subtitle: { fontSize: 13, color: Colors.textSecondary, marginBottom: Spacing.lg, lineHeight: 19 },
  mediaBanner: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, padding: Spacing.md, borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.primary, backgroundColor: Colors.surface, marginBottom: Spacing.lg },
  mediaBannerText: { flex: 1, color: Colors.text, fontSize: 13, fontWeight: '700' },
  retryBtn: { marginTop: Spacing.sm, paddingHorizontal: 18, minHeight: 44, borderRadius: 22, borderWidth: 1, borderColor: Colors.border, alignItems: 'center', justifyContent: 'center' },
  retryLabel: { color: Colors.text, fontWeight: '700', fontSize: 14 },
  primaryBtn: { marginTop: Spacing.sm, paddingHorizontal: 18, minHeight: 46, borderRadius: 23, backgroundColor: Colors.primary, alignItems: 'center', justifyContent: 'center' },
  primaryLabel: { color: Colors.background, fontWeight: '800', fontSize: 14 },
  emptyBlock: { alignItems: 'center', gap: Spacing.sm },
  empty: { color: Colors.textSecondary, fontSize: 14, paddingTop: Spacing.lg, textAlign: 'center' },
  card: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md, padding: Spacing.md, borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, marginBottom: Spacing.sm },
  cardBody: { flex: 1, gap: 2 },
  cardName: { fontSize: 15, fontWeight: '700', color: Colors.text },
  cardAddress: { fontSize: 12, color: Colors.textSecondary },
  cardDistance: { fontSize: 11, color: Colors.textSecondary, marginTop: 2 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 18, borderWidth: 1, borderColor: Colors.border, minHeight: 44 },
  actionBtnDone: { opacity: 0.6 },
  actionLabel: { fontSize: 13, fontWeight: '700', color: Colors.text },
  actionLabelDone: { color: Colors.textSecondary },
});
