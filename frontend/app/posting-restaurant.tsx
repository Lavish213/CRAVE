import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import * as Location from 'expo-location';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { Colors, Radius, Spacing, Typography } from '../src/constants/colors';
import { NearbyCandidate, confirmNewSpot, searchNearby } from '../src/api/nearby';
import { usePostingDraftStore } from '../src/stores/postingDraftStore';
import { useAuthStore } from '../src/stores/authStore';
import { useToast } from '../src/hooks/useToast';

type State = 'loading' | 'ready' | 'denied' | 'error';

export default function PostingRestaurantScreen() {
  const router = useRouter();
  const toast = useToast((s) => s.show);
  const user = useAuthStore((s) => s.user);
  const { draftId } = useLocalSearchParams<{ draftId?: string }>();
  const draft = usePostingDraftStore((s) => s.drafts.find((d) => d.id === draftId));
  const setDraftPlace = usePostingDraftStore((s) => s.setDraftPlace);
  const setDraftCandidate = usePostingDraftStore((s) => s.setDraftCandidate);
  const [state, setState] = useState<State>('loading');
  const [results, setResults] = useState<NearbyCandidate[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const permission = await Location.requestForegroundPermissionsAsync();
        if (!active) return;
        if (!permission.granted) { setState('denied'); return; }
        const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
        const found = await searchNearby(position.coords.latitude, position.coords.longitude);
        if (!active) return;
        setResults(found); setState('ready');
      } catch { if (active) setState('error'); }
    })();
    return () => { active = false; };
  }, []);

  if (!draft || !user || draft.ownerId !== user.id) return <View style={styles.center}><Text style={styles.title}>Draft unavailable</Text></View>;
  if (state === 'loading') return <View style={styles.center}><ActivityIndicator color={Colors.primary} /><Text style={styles.muted}>Finding nearby restaurants…</Text></View>;
  if (state === 'denied') return <View style={styles.center}><Ionicons name="location-outline" size={32} color={Colors.textSecondary} /><Text style={styles.title}>Choose a restaurant</Text><Text style={styles.muted}>Location is off. Your draft is safe. You can return after enabling location access.</Text></View>;
  if (state === 'error') return <View style={styles.center}><Text style={styles.title}>Couldn't load nearby places</Text><Text style={styles.muted}>Your draft is still saved. Try again when your connection is back.</Text></View>;

  async function choose(candidate: NearbyCandidate) {
    const key = candidate.external_id ?? candidate.name;
    setBusy(key);
    try {
      if (candidate.already_in_crave && candidate.place_id) {
        setDraftPlace(draft!.id, candidate.place_id);
      } else {
        const result = await confirmNewSpot({ external_id: candidate.external_id, name: candidate.name, lat: candidate.lat, lng: candidate.lng, address: candidate.address, category_hint: candidate.category_hint });
        setDraftCandidate(draft!.id, result.candidate_id, candidate.name);
        toast('Restaurant submitted. Your draft will stay saved while CRAVE confirms the place.');
      }
      router.replace({ pathname: '/posting-composer', params: { draftId: draft!.id } });
    } catch (error) {
      toast(error instanceof Error ? error.message : "Couldn't select that restaurant");
    } finally { setBusy(null); }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>RESTAURANT</Text><Text style={styles.title}>Where was this?</Text>
      <Text style={styles.muted}>Selecting a restaurant does not upload or publish your media.</Text>
      <View style={styles.list}>
        {results.length === 0 ? <Text style={styles.muted}>Nothing nearby yet. Your draft is safe.</Text> : results.map((candidate) => {
          const key = candidate.external_id ?? candidate.name;
          return <Pressable key={key} disabled={busy !== null} onPress={() => void choose(candidate)} style={styles.card} accessibilityRole="button" accessibilityLabel={`Choose ${candidate.name}`}>
            <View style={styles.cardCopy}><Text style={styles.name}>{candidate.name}</Text>{candidate.address ? <Text style={styles.address}>{candidate.address}</Text> : null}<Text style={styles.address}>{Math.round(candidate.distance_m)}m away</Text></View>
            {busy === key ? <ActivityIndicator color={Colors.primary} /> : <Ionicons name="chevron-forward" size={20} color={Colors.textSecondary} />}
          </Pressable>;
        })}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background }, content: { padding: Spacing.lg, paddingBottom: 48 }, center: { flex: 1, backgroundColor: Colors.background, alignItems: 'center', justifyContent: 'center', padding: Spacing.xl, gap: Spacing.sm },
  eyebrow: { ...Typography.caption, color: Colors.primary, fontWeight: '800', letterSpacing: 1.1 }, title: { ...Typography.title, color: Colors.text, marginTop: Spacing.xs }, muted: { ...Typography.body, color: Colors.textSecondary, textAlign: 'center' }, list: { marginTop: Spacing.xl, gap: Spacing.sm },
  card: { minHeight: 68, borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, padding: Spacing.md, flexDirection: 'row', alignItems: 'center', gap: Spacing.md }, cardCopy: { flex: 1 }, name: { ...Typography.body, color: Colors.text, fontWeight: '800' }, address: { ...Typography.caption, color: Colors.textSecondary, marginTop: 2 },
});
