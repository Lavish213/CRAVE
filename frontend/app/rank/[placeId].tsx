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
  // Distinct from opponent === null while resolving -- true only once the
  // opponent's own detail fetch has actually failed. Gates the opponent
  // card's rankability (see the comparing-stage render below): previously
  // a failed opponent fetch just left `opponent` null with no flag, and
  // the card rendered its "A place you ranked" placeholder fully
  // clickable via ComparisonChoice's onChoose -- a real, confirmed bug
  // (an unidentified place could still be voted the winner). disabled
  // only prevents that one card's tap; "Can't decide" and the just-
  // ranked place's own card stay available either way.
  const [opponentError, setOpponentError] = useState(false);
  const [stage, setStage] = useState<Stage>('tier');
  const [tier, setTier] = useState<RankTier | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [result, setResult] = useState<Ranking | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // React state alone (`busy`) can't close a fast-double-tap race -- two
  // native touch events can both reach their JS handler before either's
  // setBusy(true) has actually committed a re-render with disabled=true.
  // A ref mutates synchronously and immediately, so the *second* call in
  // the same event-loop tick still sees it, closing the gap state can't.
  const submittingRef = useRef(false);
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

  // expo-router can reuse this screen instance across a placeId change
  // rather than unmounting — without resetting state here, `place` (and the
  // rest of the ranking flow) can still hold the previous place while the
  // new placeId's fetch is in flight, showing place A's name/image while
  // handlePickTier/handleChoose below submit against the route's (new)
  // placeId — a real risk of the UI showing one place while the ranking
  // that gets recorded is for another. Reset everything up front and keep
  // rendering the loading state until the fetched place actually matches
  // the current placeId.
  const placeGenerationRef = useRef(0);

  const loadPlace = useCallback((id: string, myGeneration: number) => {
    setError(null);
    fetchPlaceDetail(id)
      .then((p) => {
        if (myGeneration !== placeGenerationRef.current) return;
        setPlace(p);
      })
      .catch(() => {
        if (myGeneration !== placeGenerationRef.current) return;
        setError("Couldn't load this place.");
      });
  }, []);

  useEffect(() => {
    if (!placeId) return;
    const myGeneration = ++placeGenerationRef.current;
    // A submission still in flight for the *previous* place must not go
    // on blocking this (new) place's own tier/comparison controls until
    // that stale request happens to settle -- its own generation check
    // already keeps its result from being applied, but the lock itself
    // needs releasing here too, not left to that unrelated `finally`.
    submittingRef.current = false;
    setPlace(null);
    setError(null);
    setOpponent(null);
    setOpponentError(false);
    setStage('tier');
    setTier(null);
    setToken(null);
    setResult(null);
    setRound(0);
    setBeatOpponentName(null);
    loadPlace(placeId, myGeneration);
  }, [placeId, loadPlace]);

  // The opponent id from the most recent comparison step -- kept
  // separately from the resolved `opponent` object so a failed detail
  // fetch still has something for handleRetryOpponent to re-fetch.
  const opponentPlaceIdRef = useRef<string | null>(null);

  const loadOpponent = useCallback(async (opponentPlaceId: string, myGeneration: number) => {
    setOpponentError(false);
    try {
      const resolved = await fetchPlaceDetail(opponentPlaceId);
      if (myGeneration !== placeGenerationRef.current) return;
      setOpponent(resolved);
    } catch {
      if (myGeneration !== placeGenerationRef.current) return;
      // The backend already knows this opponent (it's in the signed
      // token) -- only its display detail failed to resolve. Previously
      // this left `opponent` at null with no distinguishing flag, and
      // the comparing-stage card rendered its "A place you ranked"
      // placeholder fully clickable: an unidentified place could still
      // be submitted as the winner. Never fabricate that outcome --
      // disable the card instead (see the render below) and offer a
      // real retry rather than silently degrading to a plainer card.
      setOpponent(null);
      setOpponentError(true);
    }
  }, []);

  const handleRetryOpponent = () => {
    if (!opponentPlaceIdRef.current) return;
    loadOpponent(opponentPlaceIdRef.current, placeGenerationRef.current);
  };

  /** Both entry points (start + each answer) return the same shape. */
  const applyStep = useCallback(async (step: RankingStep, myGeneration: number) => {
    // Late work from a previous placeId (e.g. a submission that was
    // still in flight when the route moved to a different place) must
    // never commit its result under the place this screen now shows.
    if (myGeneration !== placeGenerationRef.current) return;

    if (step.status === 'ranked') {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setResult(step.ranking);
      setStage('done');
      setToken(null);
      setOpponent(null);
      setOpponentError(false);
      opponentPlaceIdRef.current = null;
      return;
    }

    setToken(step.comparison_token);
    setStage('comparing');
    setRound((r) => r + 1);
    opponentPlaceIdRef.current = step.opponent_place_id;

    // The backend returns only an id — the head-to-head needs a photo and a
    // name to be a real comparison, so resolve it.
    await loadOpponent(step.opponent_place_id, myGeneration);
  }, [loadOpponent]);

  const handlePickTier = async (picked: RankTier) => {
    if (!placeId || submittingRef.current) return;
    const myGeneration = placeGenerationRef.current;
    submittingRef.current = true;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setBusy(true);
    setError(null);
    setTier(picked);
    try {
      await applyStep(await startRanking({ place_id: placeId, tier: picked }), myGeneration);
    } catch (err: any) {
      if (myGeneration !== placeGenerationRef.current) return;
      const detail = err?.response?.data?.detail;
      setError(detail ?? "Couldn't start ranking this place.");
      setStage('tier');
      setTier(null);
    } finally {
      submittingRef.current = false;
      setBusy(false);
    }
  };

  const handleChoose = async (winner: 'new' | 'opponent' | 'skip') => {
    // A failed-to-resolve opponent must never be submittable as a winner
    // -- this is the same rule the comparing-stage card's own `disabled`
    // enforces, checked again here so nothing (a stale ref, a timing
    // quirk) can route around it.
    if (!token || submittingRef.current || (winner === 'opponent' && (opponentError || !opponent))) return;
    const myGeneration = placeGenerationRef.current;
    submittingRef.current = true;
    setBusy(true);
    setError(null);
    if (winner === 'new' && opponent) {
      setBeatOpponentName(opponent.name);
    }
    try {
      await applyStep(await submitComparison(token, winner), myGeneration);
    } catch (err: any) {
      if (myGeneration !== placeGenerationRef.current) return;
      const detail = err?.response?.data?.detail;
      setError(detail ?? "Couldn't record that comparison.");
    } finally {
      submittingRef.current = false;
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
        <Ionicons name="person-circle-outline" size={44} color={Colors.textSecondary} />
        <Text style={styles.emptyTitle}>Sign in to rank places</Text>
        <Text style={styles.emptyBody}>
          Your rankings are personal — they build your own ordered list.
        </Text>
      </View>
    );
  }

  if (error && stage === 'tier' && !place) {
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          if (!placeId) return;
          loadPlace(placeId, placeGenerationRef.current);
        }}
      />
    );
  }

  // place.id !== placeId (not just !place) — between a placeId change and
  // the new place resolving, `place` briefly holds nothing (it's reset
  // above), but this also holds the line even if that ever changes, so a
  // stale previous place can never render under the new route's placeId.
  if (!place || place.id !== placeId) {
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
            onPress={() => router.push('/profile')}
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
            name={opponentError ? 'Unavailable' : (opponent?.name ?? 'A place you ranked')}
            imageUrl={opponent?.primary_image_url ?? opponent?.image}
            category={opponent?.category}
            badge={opponentError ? "Couldn't load" : 'Already ranked'}
            // Never rankable while unidentified -- opponentError, or a
            // still-resolving opponent (opponent === null the moment
            // this stage first renders, before its own fetch settles),
            // must not be votable. "Can't decide" below stays available
            // either way.
            onChoose={() => handleChoose('opponent')}
            disabled={busy || opponentError || !opponent}
          />

          {opponentError ? (
            <TouchableOpacity
              style={styles.opponentRetryBtn}
              onPress={handleRetryOpponent}
              disabled={busy}
              accessibilityRole="button"
              accessibilityLabel="Retry loading the other place"
            >
              <Ionicons name="refresh" size={14} color={Colors.primary} />
              <Text style={styles.opponentRetryText}>Couldn't load that place — retry</Text>
            </TouchableOpacity>
          ) : null}

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
            <Ionicons name="chevron-forward" size={18} color={Colors.textSecondary} />
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
    color: Colors.textSecondary,
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
    color: Colors.textSecondary,
    fontSize: 13,
    lineHeight: 19,
    marginTop: Spacing.xl,
  },

  // Stage 2
  compareHeader: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.lg },
  compareTitle: { color: Colors.text, fontSize: 24, fontWeight: '800' },
  compareSub: { color: Colors.textSecondary, fontSize: 13, marginTop: Spacing.xs },
  compareBody: { flex: 1, padding: Spacing.lg, gap: Spacing.sm },
  vsRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  vsLine: { flex: 1, height: 1, backgroundColor: Colors.border },
  vsText: {
    color: Colors.textSecondary,
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
  skipBtnText: { color: Colors.textSecondary, fontSize: 13, fontWeight: '600' },
  opponentRetryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: Spacing.sm,
    minHeight: 44,
  },
  opponentRetryText: { color: Colors.primary, fontSize: 13, fontWeight: '700' },
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
    color: Colors.textSecondary,
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
