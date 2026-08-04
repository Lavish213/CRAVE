// app/rank/[placeId].tsx
//
// "I ate here" → rank it. Three stages in one screen:
//
//   1. tier    — Loved it / It was fine / Didn't like it
//   2. compare — head-to-head against places already in that tier, which
//                binary-inserts this one into the user's personal list
//   3. done    — the resulting 0-10 score
//
// The comparison loop is driven entirely by the backend: each answer
// POSTs the signed token back and gets either the next opponent or the
// finished ranking. The client never computes a position itself.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import * as Sharing from 'expo-sharing';
import { captureRef } from 'react-native-view-shot';

import { Colors, Radius, Spacing } from '../../src/constants/colors';
import { ComparisonChoice } from '../../src/components/ComparisonChoice';
import { ErrorState } from '../../src/components/ErrorState';
import { ShareRankCard } from '../../src/components/ShareRankCard';
import { fetchPlaceDetail, PlaceOut } from '../../src/api/places';
import {
  RankTier,
  Ranking,
  RankingStep,
  startRanking,
  submitComparison,
} from '../../src/api/social';
import {
  TIER_CHOICES,
  TIER_LABELS,
  formatScore,
  tierColor,
} from '../../src/utils/rankScore';
import { useAuthStore } from '../../src/stores/authStore';

type Stage = 'tier' | 'comparing' | 'done';

export default function RankPlaceScreen() {
  const { placeId } = useLocalSearchParams<{ placeId: string }>();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  const [place, setPlace] = useState<PlaceOut | null>(null);
  const [opponent, setOpponent] = useState<PlaceOut | null>(null);
  const [stage, setStage] = useState<Stage>('tier');
  const [tier, setTier] = useState<RankTier | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [result, setResult] = useState<Ranking | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Only ever counts up — the exact number of remaining comparisons isn't
  // known ahead of time (it depends on how the binary search splits), so
  // showing "3 of 4" would be a guess. "Comparison 3" is honest.
  const [round, setRound] = useState(0);
  // The opponent from the last comparison actually won (not skipped, not
  // lost) — the backend doesn't persist comparison history, only the final
  // position, so this is the one piece of "what did it beat" the share
  // card can honestly show without inventing a stat the app doesn't track.
  const [beatOpponentName, setBeatOpponentName] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);
  const shareCardRef = useRef<View>(null);

  useEffect(() => {
    if (!placeId) return;
    fetchPlaceDetail(placeId)
      .then(setPlace)
      .catch(() => setError("Couldn't load this place."));
  }, [placeId]);

  /** Both entry points (start + each answer) return the same shape. */
  const applyStep = useCallback(async (step: RankingStep) => {
    if (step.status === 'ranked') {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setResult(step.ranking);
      setStage('done');
      setToken(null);
      setOpponent(null);
      return;
    }

    setToken(step.comparison_token);
    setStage('comparing');
    setRound((r) => r + 1);

    // The backend returns only an id — the head-to-head needs a photo and a
    // name to be a real comparison, so resolve it. A failure here still
    // leaves a usable (if plainer) card rather than blocking the flow.
    try {
      setOpponent(await fetchPlaceDetail(step.opponent_place_id));
    } catch {
      setOpponent(null);
    }
  }, []);

  const handlePickTier = async (picked: RankTier) => {
    if (!placeId || busy) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setBusy(true);
    setError(null);
    setTier(picked);
    try {
      await applyStep(await startRanking({ place_id: placeId, tier: picked }));
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(detail ?? "Couldn't start ranking this place.");
      setStage('tier');
      setTier(null);
    } finally {
      setBusy(false);
    }
  };

  const handleChoose = async (winner: 'new' | 'opponent' | 'skip') => {
    if (!token || busy) return;
    setBusy(true);
    setError(null);
    if (winner === 'new' && opponent) {
      setBeatOpponentName(opponent.name);
    }
    try {
      await applyStep(await submitComparison(token, winner));
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(detail ?? "Couldn't record that comparison.");
    } finally {
      setBusy(false);
    }
  };

  const handleShare = async () => {
    if (sharing) return;
    setSharing(true);
    try {
      const uri = await captureRef(shareCardRef, { format: 'png', quality: 1 });
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, { mimeType: 'image/png', dialogTitle: 'Share your ranking' });
      }
    } catch {
      // Best-effort — a failed share shouldn't block anything else on this
      // screen, there's nothing else useful to do with the error here.
    } finally {
      setSharing(false);
    }
  };

  if (!user) {
    return (
      <View style={styles.centered}>
        <Ionicons name="person-circle-outline" size={44} color={Colors.textMuted} />
        <Text style={styles.emptyTitle}>Sign in to rank places</Text>
        <Text style={styles.emptyBody}>
          Your rankings are personal — they build your own ordered list.
        </Text>
      </View>
    );
  }

  if (error && stage === 'tier' && !place) {
    return <ErrorState message={error} onRetry={() => router.back()} />;
  }

  if (!place) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={Colors.primary} size="large" />
      </View>
    );
  }

  // -------------------------------------------------------------------
  // Stage 3 — result
  // -------------------------------------------------------------------
  if (stage === 'done' && result) {
    const areaName = place.address ? place.address.split(',').pop()?.trim() ?? null : null;

    return (
      <View style={styles.container}>
        <View style={styles.doneWrap}>
          <View style={styles.scoreBlock}>
            <Text style={styles.scoreValue}>{formatScore(result.rank_score)}</Text>
            <Text style={styles.scoreOutOf}>OUT OF 10</Text>
          </View>

          <Text style={styles.doneName}>{place.name}</Text>
          <Text style={[styles.doneTier, { color: tierColor(result.tier) }]}>
            {TIER_LABELS[result.tier]}
          </Text>
          <Text style={styles.doneBody}>
            Added to your list. Your score comes from where it landed against
            the places you've already ranked — not a star you picked.
          </Text>

          <TouchableOpacity
            style={styles.primaryBtn}
            onPress={() => router.replace('/profile')}
            accessibilityRole="button"
            accessibilityLabel="See my list"
          >
            <Text style={styles.primaryBtnText}>See my list</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.shareBtn}
            onPress={handleShare}
            disabled={sharing}
            accessibilityRole="button"
            accessibilityLabel="Share this ranking"
          >
            {sharing ? (
              <ActivityIndicator color={Colors.text} size="small" />
            ) : (
              <>
                <Ionicons name="share-outline" size={16} color={Colors.text} />
                <Text style={styles.shareBtnText}>Share</Text>
              </>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.secondaryBtn}
            onPress={() => router.back()}
            accessibilityRole="button"
            accessibilityLabel="Done"
          >
            <Text style={styles.secondaryBtnText}>Done</Text>
          </TouchableOpacity>
        </View>

        {/* Off-screen (not display:none — that would skip layout entirely
            and captureRef needs a real, measured view to snapshot). */}
        <View style={styles.shareCardOffscreen} pointerEvents="none">
          <ShareRankCard
            ref={shareCardRef}
            name={place.name}
            category={place.category}
            areaName={areaName}
            imageUrl={place.primary_image_url ?? place.image}
            score={result.rank_score}
            tier={result.tier}
            beatName={beatOpponentName}
          />
        </View>
      </View>
    );
  }

  // -------------------------------------------------------------------
  // Stage 2 — head-to-head
  // -------------------------------------------------------------------
  if (stage === 'comparing') {
    return (
      <View style={styles.container}>
        <View style={styles.compareHeader}>
          <Text style={styles.compareTitle}>Which was better?</Text>
          <Text style={styles.compareSub}>
            Comparison {round} · this is what sets your score
          </Text>
        </View>

        {error ? <Text style={styles.inlineError}>{error}</Text> : null}

        <View style={styles.compareBody}>
          <ComparisonChoice
            name={place.name}
            imageUrl={place.primary_image_url ?? place.image}
            category={place.category}
            badge="Just visited"
            onChoose={() => handleChoose('new')}
            disabled={busy}
          />

          <View style={styles.vsRow}>
            <View style={styles.vsLine} />
            <Text style={styles.vsText}>OR</Text>
            <View style={styles.vsLine} />
          </View>

          <ComparisonChoice
            name={opponent?.name ?? 'A place you ranked'}
            imageUrl={opponent?.primary_image_url ?? opponent?.image}
            category={opponent?.category}
            badge="Already ranked"
            onChoose={() => handleChoose('opponent')}
            disabled={busy}
          />

          <TouchableOpacity
            style={styles.skipBtn}
            onPress={() => handleChoose('skip')}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel="Can't decide"
          >
            <Text style={styles.skipBtnText}>Can't decide — too close to call</Text>
          </TouchableOpacity>
        </View>

        {busy ? (
          <View style={styles.busyOverlay} pointerEvents="none">
            <ActivityIndicator color={Colors.primary} />
          </View>
        ) : null}
      </View>
    );
  }

  // -------------------------------------------------------------------
  // Stage 1 — tier
  // -------------------------------------------------------------------
  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.tierScroll}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.tierEyebrow}>You ate at</Text>
      <Text style={styles.tierPlaceName}>{place.name}</Text>
      <Text style={styles.tierPrompt}>How was it?</Text>

      {error ? <Text style={styles.inlineError}>{error}</Text> : null}

      <View style={styles.tierList}>
        {TIER_CHOICES.map((choice) => (
          <TouchableOpacity
            key={choice.tier}
            style={[
              styles.tierBtn,
              tier === choice.tier ? { borderColor: tierColor(choice.tier) } : null,
            ]}
            onPress={() => handlePickTier(choice.tier)}
            disabled={busy}
            activeOpacity={0.8}
            accessibilityRole="button"
            accessibilityLabel={choice.label}
          >
            <View
              style={[styles.tierIcon, { backgroundColor: tierColor(choice.tier) + '22' }]}
            >
              <Ionicons
                name={choice.icon as any}
                size={20}
                color={tierColor(choice.tier)}
              />
            </View>
            <Text style={styles.tierBtnText}>{choice.label}</Text>
            <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.tierFootnote}>
        You'll compare it against a few places you've already ranked — that's
        what turns this into a real score instead of a star rating everyone
        inflates.
      </Text>

      {busy ? <ActivityIndicator color={Colors.primary} style={{ marginTop: Spacing.lg }} /> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.background,
    gap: Spacing.sm,
    padding: Spacing.xl,
  },
  emptyTitle: { color: Colors.text, fontSize: 18, fontWeight: '700' },
  emptyBody: { color: Colors.textSecondary, fontSize: 14, textAlign: 'center' },

  inlineError: {
    color: Colors.error,
    fontSize: 13,
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.sm,
  },

  // Stage 1
  tierScroll: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  tierEyebrow: {
    color: Colors.textMuted,
    fontSize: 13,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  tierPlaceName: {
    color: Colors.text,
    fontSize: 26,
    fontWeight: '800',
    marginTop: Spacing.xs,
  },
  tierPrompt: {
    color: Colors.textSecondary,
    fontSize: 16,
    marginTop: Spacing.lg,
    marginBottom: Spacing.md,
  },
  tierList: { gap: Spacing.sm },
  tierBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    padding: Spacing.lg,
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    borderWidth: 1.5,
    borderColor: Colors.border,
    minHeight: 64,
  },
  tierIcon: {
    width: 38,
    height: 38,
    borderRadius: Radius.full,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tierBtnText: { flex: 1, color: Colors.text, fontSize: 16, fontWeight: '700' },
  tierFootnote: {
    color: Colors.textMuted,
    fontSize: 13,
    lineHeight: 19,
    marginTop: Spacing.xl,
  },

  // Stage 2
  compareHeader: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.lg },
  compareTitle: { color: Colors.text, fontSize: 24, fontWeight: '800' },
  compareSub: { color: Colors.textMuted, fontSize: 13, marginTop: Spacing.xs },
  compareBody: { flex: 1, padding: Spacing.lg, gap: Spacing.sm },
  vsRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  vsLine: { flex: 1, height: 1, backgroundColor: Colors.border },
  vsText: {
    color: Colors.textMuted,
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1,
  },
  skipBtn: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Spacing.sm,
    minHeight: 40,
  },
  skipBtnText: { color: Colors.textMuted, fontSize: 13, fontWeight: '600' },
  busyOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.25)',
  },

  // Stage 3
  doneWrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xl,
    gap: Spacing.sm,
  },
  scoreBlock: {
    alignItems: 'center',
    marginBottom: Spacing.lg,
  },
  scoreValue: { color: Colors.text, fontSize: 56, fontWeight: '800', lineHeight: 60 },
  scoreOutOf: {
    color: Colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.8,
    marginTop: 6,
  },
  doneName: { color: Colors.text, fontSize: 22, fontWeight: '800', textAlign: 'center' },
  doneTier: { fontSize: 15, fontWeight: '700' },
  doneBody: {
    color: Colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
    marginTop: Spacing.sm,
    marginBottom: Spacing.lg,
  },
  primaryBtn: {
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.xl,
    paddingVertical: 14,
    borderRadius: Radius.pill,
    minHeight: 48,
    justifyContent: 'center',
    alignSelf: 'stretch',
    alignItems: 'center',
  },
  primaryBtnText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  shareBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.pill,
    minHeight: 46,
    alignSelf: 'stretch',
    marginTop: Spacing.sm,
  },
  shareBtnText: { color: Colors.text, fontSize: 14, fontWeight: '700' },
  shareCardOffscreen: { position: 'absolute', top: 0, left: -9999 },
  secondaryBtn: {
    paddingHorizontal: Spacing.xl,
    paddingVertical: 12,
    minHeight: 44,
    justifyContent: 'center',
  },
  secondaryBtnText: { color: Colors.textSecondary, fontSize: 14, fontWeight: '600' },
});
