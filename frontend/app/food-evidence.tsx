import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';

import { searchPlaces } from '../src/api/search';
import type { PlaceOut } from '../src/api/places';
import { Colors, Radius, Spacing, Typography } from '../src/constants/colors';
import { AuthSheet } from '../src/components/AuthSheet';
import { useAuthStore } from '../src/stores/authStore';
import {
  DraftIntent,
  DraftMediaKind,
  DraftReaction,
  DraftVisibility,
  PostingDraft,
  usePostingDraftStore,
} from '../src/stores/postingDraftStore';
import { useToast } from '../src/hooks/useToast';

type Step = 'intent' | 'media' | 'preview' | 'restaurant' | 'reaction' | 'caption' | 'visibility' | 'review';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

function recoveryStep(draft: PostingDraft): Step {
  if (!draft.localUri && draft.intent === 'social_post') return 'media';
  if (draft.restaurantRef.type !== 'place') return 'restaurant';
  return 'reaction';
}

export default function FoodEvidenceScreen() {
  const router = useRouter();
  const { draftId: routeDraftId } = useLocalSearchParams<{ draftId?: string }>();
  const user = useAuthStore((state) => state.user);
  const toast = useToast((state) => state.show);

  const drafts = usePostingDraftStore((state) => state.drafts);
  const createDraft = usePostingDraftStore((state) => state.createDraft);
  const addMediaToDraft = usePostingDraftStore((state) => state.addMediaToDraft);
  const setDraftPlace = usePostingDraftStore((state) => state.setDraftPlace);
  const setDraftReaction = usePostingDraftStore((state) => state.setDraftReaction);
  const setDraftCaption = usePostingDraftStore((state) => state.setDraftCaption);
  const setDraftVisibility = usePostingDraftStore((state) => state.setDraftVisibility);
  const commitDraft = usePostingDraftStore((state) => state.commitDraft);
  const deleteDraft = usePostingDraftStore((state) => state.deleteDraft);

  const ownedDrafts = useMemo(
    () => (user ? drafts.filter((draft) => draft.ownerId === user.id) : []),
    [drafts, user],
  );
  const initialDraft = routeDraftId
    ? ownedDrafts.find((draft) => draft.id === routeDraftId)
    : ownedDrafts[0];

  const [activeDraftId, setActiveDraftId] = useState<string | null>(initialDraft?.id ?? null);
  const activeDraft = ownedDrafts.find((draft) => draft.id === activeDraftId) ?? null;
  const [step, setStep] = useState<Step>(activeDraft ? recoveryStep(activeDraft) : 'intent');
  const [mediaMode, setMediaMode] = useState<DraftMediaKind>('photo');
  const [savingMedia, setSavingMedia] = useState(false);
  const [authVisible, setAuthVisible] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<PlaceOut[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!routeDraftId || activeDraftId === routeDraftId) return;
    const routeDraft = ownedDrafts.find((draft) => draft.id === routeDraftId);
    if (!routeDraft) return;
    setActiveDraftId(routeDraft.id);
    setStep(recoveryStep(routeDraft));
  }, [activeDraftId, ownedDrafts, routeDraftId]);

  if (!user) {
    return (
      <View style={[styles.screen, styles.centered]}>
        <Ionicons name="restaurant-outline" size={42} color={Colors.primary} />
        <Text style={styles.title}>Add to CRAVE</Text>
        <Text style={styles.body}>Sign in before CRAVE saves a private log or post to your account.</Text>
        <PrimaryButton label="Sign in" onPress={() => setAuthVisible(true)} />
        <AuthSheet visible={authVisible} onClose={() => setAuthVisible(false)} reason="default" />
      </View>
    );
  }

  function begin(intent: DraftIntent) {
    const draft = createDraft(user!.id, intent);
    setActiveDraftId(draft.id);
    setStep('media');
  }

  async function persistAsset(asset: ImagePicker.ImagePickerAsset, kind: DraftMediaKind) {
    if (!activeDraft) return;
    setSavingMedia(true);
    try {
      await addMediaToDraft(activeDraft.id, {
        sourceUri: asset.uri,
        kind,
        mimeType: asset.mimeType,
        fileSize: asset.fileSize,
      });
      setStep('preview');
    } catch (error) {
      toast(error instanceof Error ? error.message : "Couldn't save that media");
    } finally {
      setSavingMedia(false);
    }
  }

  async function openCamera() {
    if (!activeDraft) return;
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Camera unavailable', 'You can still choose a photo or video from your library.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: mediaMode === 'photo' ? ['images'] : ['videos'],
      allowsEditing: false,
      quality: mediaMode === 'photo' ? 0.9 : 1,
      videoMaxDuration: 10,
    });
    const asset = !result.canceled ? result.assets[0] : undefined;
    if (asset?.uri) await persistAsset(asset, mediaMode);
  }

  async function openLibrary() {
    if (!activeDraft) return;
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images', 'videos'],
      allowsEditing: false,
      quality: 0.9,
    });
    const asset = !result.canceled ? result.assets[0] : undefined;
    if (!asset?.uri) return;
    const kind: DraftMediaKind = asset.type === 'video' ? 'video' : 'photo';
    await persistAsset(asset, kind);
  }

  async function runRestaurantSearch() {
    const query = searchText.trim();
    if (query.length < 2) {
      toast('Type at least two letters to search restaurants.');
      return;
    }
    setSearching(true);
    try {
      const result = await searchPlaces({ query, page_size: 8 });
      setSearchResults(result.items);
    } catch (error) {
      toast(error instanceof Error ? error.message : "Couldn't search restaurants");
    } finally {
      setSearching(false);
    }
  }

  function choosePlace(place: PlaceOut) {
    if (!activeDraft) return;
    setDraftPlace(activeDraft.id, place.id, place.name);
    setSearchResults([]);
    setSearchText('');
    setStep('reaction');
  }

  async function finish() {
    if (!activeDraft) return;
    setSubmitting(true);
    try {
      const result = await commitDraft(activeDraft.id);
      if (result) router.back();
    } finally {
      setSubmitting(false);
    }
  }

  async function discard() {
    if (!activeDraft) return;
    await deleteDraft(activeDraft.id);
    setActiveDraftId(null);
    setStep('intent');
  }

  if (!activeDraft || step === 'intent') {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <Text style={styles.eyebrow}>ADD TO CRAVE</Text>
        <Text style={styles.heroTitle}>What are you doing?</Text>
        <Text style={styles.body}>Logging and sharing use the same food evidence, but they are different outcomes.</Text>
        <ChoiceCard
          icon="lock-closed-outline"
          title="Log what I ate"
          body="Private food history. Media is optional."
          onPress={() => begin('private_log')}
        />
        <ChoiceCard
          icon="sparkles-outline"
          title="Share a food find"
          body="Share intentionally with your chosen audience. Media is required."
          onPress={() => begin('social_post')}
        />
        {ownedDrafts.length > 0 ? (
          <View style={styles.resumeBlock}>
            <Text style={styles.sectionLabel}>YOUR DRAFTS</Text>
            {ownedDrafts.slice(0, 3).map((draft) => (
              <Pressable
                key={draft.id}
                style={styles.resumeRow}
                onPress={() => {
                  setActiveDraftId(draft.id);
                  setStep(recoveryStep(draft));
                }}
                accessibilityRole="button"
              >
                <Ionicons name={draft.kind === 'video' ? 'videocam-outline' : draft.kind === 'photo' ? 'image-outline' : 'restaurant-outline'} size={20} color={Colors.primary} />
                <View style={styles.flex}>
                  <Text style={styles.resumeTitle}>{draft.restaurantRef.type === 'candidate' ? draft.restaurantRef.displayName : draft.restaurantRef.type === 'place' ? draft.restaurantRef.displayName ?? 'Restaurant selected' : 'Unfinished meal'}</Text>
                  <Text style={styles.caption}>{draft.intent === 'private_log' ? 'Private log' : 'Food find'} · Continue</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={Colors.textSecondary} />
              </Pressable>
            ))}
          </View>
        ) : null}
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.topRow}>
        <Text style={styles.eyebrow}>{activeDraft.intent === 'private_log' ? 'PRIVATE LOG' : 'FOOD FIND'}</Text>
        <Pressable onPress={() => void discard()} accessibilityRole="button" accessibilityLabel="Delete draft" hitSlop={10}>
          <Text style={styles.deleteText}>Delete draft</Text>
        </Pressable>
      </View>

      {activeDraft.lastError ? (
        <View style={styles.warning} accessibilityRole="alert">
          <Ionicons name="alert-circle-outline" size={18} color={Colors.textSecondary} />
          <Text style={styles.warningText}>{activeDraft.lastError}</Text>
        </View>
      ) : null}

      {step === 'media' ? (
        <>
          <Text style={styles.heroTitle}>Add the food</Text>
          <Text style={styles.body}>Capture once. CRAVE saves accepted media locally before you identify the restaurant.</Text>
          <View style={styles.modeRow}>
            <ModeButton label="Photo" selected={mediaMode === 'photo'} onPress={() => setMediaMode('photo')} />
            <ModeButton label="Video" selected={mediaMode === 'video'} onPress={() => setMediaMode('video')} />
          </View>
          <View style={styles.captureStage}>
            <Ionicons name={mediaMode === 'photo' ? 'camera-outline' : 'videocam-outline'} size={54} color={Colors.text} />
            <Text style={styles.captureTitle}>{mediaMode === 'photo' ? 'Photograph the food' : 'Record up to 10 seconds'}</Text>
            <PrimaryButton label={savingMedia ? 'Saving…' : mediaMode === 'photo' ? 'Take photo' : 'Record video'} onPress={() => void openCamera()} disabled={savingMedia} />
            <SecondaryButton label="Choose from library" onPress={() => void openLibrary()} disabled={savingMedia} />
          </View>
          {activeDraft.intent === 'private_log' ? <TextButton label="Skip media" onPress={() => setStep('restaurant')} /> : null}
        </>
      ) : null}

      {step === 'preview' ? (
        <>
          <Text style={styles.heroTitle}>Keep this?</Text>
          {activeDraft.kind === 'photo' && activeDraft.localUri ? (
            <Image source={{ uri: activeDraft.localUri }} style={styles.previewImage} resizeMode="cover" accessibilityLabel="Selected food photo" />
          ) : (
            <View style={styles.videoPreview}>
              <Ionicons name="play-circle-outline" size={64} color={Colors.text} />
              <Text style={styles.captureTitle}>Video saved</Text>
              <Text style={styles.caption}>Your clip is safely stored on this device.</Text>
            </View>
          )}
          <PrimaryButton label={activeDraft.kind === 'video' ? 'Use video' : 'Use photo'} onPress={() => setStep('restaurant')} />
          <SecondaryButton label="Replace media" onPress={() => setStep('media')} />
        </>
      ) : null}

      {step === 'restaurant' ? (
        <>
          <Text style={styles.heroTitle}>Where was this?</Text>
          {activeDraft.restaurantRef.type === 'candidate' ? (
            <View style={styles.pendingCard}>
              <Ionicons name="time-outline" size={22} color={Colors.primary} />
              <View style={styles.flex}>
                <Text style={styles.cardTitle}>{activeDraft.restaurantRef.displayName}</Text>
                <Text style={styles.caption}>We're verifying this restaurant. Your draft and media stay saved.</Text>
              </View>
            </View>
          ) : null}
          <View style={styles.searchRow}>
            <TextInput
              value={searchText}
              onChangeText={setSearchText}
              onSubmitEditing={() => void runRestaurantSearch()}
              placeholder="Search restaurant name"
              placeholderTextColor={Colors.textSecondary}
              style={styles.searchInput}
              returnKeyType="search"
              accessibilityLabel="Search restaurant name"
            />
            <Pressable style={styles.searchButton} onPress={() => void runRestaurantSearch()} accessibilityRole="button">
              {searching ? <ActivityIndicator color={Colors.background} /> : <Ionicons name="search" size={20} color={Colors.background} />}
            </Pressable>
          </View>
          {searchResults.map((place) => (
            <Pressable key={place.id} style={styles.placeRow} onPress={() => choosePlace(place)} accessibilityRole="button">
              <View style={styles.flex}>
                <Text style={styles.cardTitle}>{place.name}</Text>
                {place.address ? <Text style={styles.caption} numberOfLines={1}>{place.address}</Text> : null}
              </View>
              <Text style={styles.selectText}>Select</Text>
            </Pressable>
          ))}
          {searchResults.length === 0 && searchText.trim().length >= 2 && !searching ? (
            <Text style={styles.caption}>No exact restaurant yet? You can submit a missing place without losing this draft.</Text>
          ) : null}
          <SecondaryButton
            label="Can't find it? Add this place"
            onPress={() => router.push({ pathname: '/add-spot', params: { draftId: activeDraft.id } })}
          />
          {activeDraft.restaurantRef.type === 'candidate' ? <TextButton label="Finish later" onPress={() => router.back()} /> : null}
        </>
      ) : null}

      {step === 'reaction' ? (
        <>
          <Text style={styles.heroTitle}>How was it?</Text>
          <Text style={styles.body}>This reaction is explicit taste evidence. Posting a photo by itself never means you liked the restaurant.</Text>
          {(['loved', 'good', 'not_for_me'] as DraftReaction[]).map((reaction) => (
            <ChoiceCard
              key={reaction}
              icon={reaction === 'loved' ? 'heart-outline' : reaction === 'good' ? 'thumbs-up-outline' : 'thumbs-down-outline'}
              title={reaction === 'loved' ? 'Loved it' : reaction === 'good' ? 'Good' : 'Not for me'}
              selected={activeDraft.reaction === reaction}
              onPress={() => {
                setDraftReaction(activeDraft.id, reaction);
                setStep('caption');
              }}
            />
          ))}
          <TextButton label="Skip" onPress={() => { setDraftReaction(activeDraft.id, null); setStep('caption'); }} />
        </>
      ) : null}

      {step === 'caption' ? (
        <>
          <Text style={styles.heroTitle}>Anything worth remembering?</Text>
          <Text style={styles.body}>Optional. A quick note is enough; CRAVE does not require a review.</Text>
          <TextInput
            value={activeDraft.caption}
            onChangeText={(value) => setDraftCaption(activeDraft.id, value)}
            placeholder="spicy but incredible…"
            placeholderTextColor={Colors.textSecondary}
            multiline
            maxLength={2000}
            style={styles.captionInput}
            accessibilityLabel="Optional note about the meal"
          />
          <PrimaryButton label="Continue" onPress={() => setStep(activeDraft.intent === 'private_log' ? 'review' : 'visibility')} />
          <TextButton label="Skip note" onPress={() => { setDraftCaption(activeDraft.id, ''); setStep(activeDraft.intent === 'private_log' ? 'review' : 'visibility'); }} />
        </>
      ) : null}

      {step === 'visibility' ? (
        <>
          <Text style={styles.heroTitle}>Who can see this?</Text>
          <Text style={styles.body}>Choose deliberately. Uploading the media did not publish it.</Text>
          <ChoiceCard
            icon="people-outline"
            title="Connections"
            body="Share with your approved CRAVE connections."
            selected={activeDraft.visibility === 'connections'}
            onPress={() => { setDraftVisibility(activeDraft.id, 'connections'); setStep('review'); }}
          />
          <ChoiceCard
            icon="globe-outline"
            title="Public"
            body="Visible on eligible CRAVE community surfaces."
            selected={activeDraft.visibility === 'public'}
            onPress={() => { setDraftVisibility(activeDraft.id, 'public'); setStep('review'); }}
          />
        </>
      ) : null}

      {step === 'review' ? (
        <>
          <Text style={styles.heroTitle}>{activeDraft.intent === 'private_log' ? 'Save privately' : 'Ready to post?'}</Text>
          <View style={styles.reviewCard}>
            <ReviewRow label="Restaurant" value={activeDraft.restaurantRef.type === 'place' ? activeDraft.restaurantRef.displayName ?? 'Selected restaurant' : 'Not resolved'} />
            <ReviewRow label="Media" value={activeDraft.kind === 'video' ? 'Video' : activeDraft.kind === 'photo' ? 'Photo' : 'None'} />
            <ReviewRow label="Reaction" value={activeDraft.reaction === 'loved' ? 'Loved it' : activeDraft.reaction === 'good' ? 'Good' : activeDraft.reaction === 'not_for_me' ? 'Not for me' : 'Skipped'} />
            <ReviewRow label="Visibility" value={activeDraft.intent === 'private_log' ? 'Just me' : activeDraft.visibility === 'public' ? 'Public' : 'Connections'} />
          </View>
          <PrimaryButton
            label={submitting ? 'Finishing…' : activeDraft.intent === 'private_log' ? 'Save privately' : activeDraft.visibility === 'public' ? 'Post publicly' : 'Share with connections'}
            onPress={() => void finish()}
            disabled={submitting || activeDraft.outcome === 'committing'}
          />
          <SecondaryButton label="Back" onPress={() => setStep(activeDraft.intent === 'private_log' ? 'caption' : 'visibility')} disabled={submitting} />
          <Text style={styles.privacyNote}>If the network fails, CRAVE keeps this draft and its local media so you can retry without recapturing.</Text>
        </>
      ) : null}
    </ScrollView>
  );
}

function PrimaryButton({ label, onPress, disabled = false }: { label: string; onPress: () => void; disabled?: boolean }) {
  return (
    <Pressable
      style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed, disabled && styles.disabled]}
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityState={{ disabled }}
    >
      <Text style={styles.primaryLabel}>{label}</Text>
    </Pressable>
  );
}

function SecondaryButton({ label, onPress, disabled = false }: { label: string; onPress: () => void; disabled?: boolean }) {
  return (
    <Pressable
      style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed, disabled && styles.disabled]}
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityState={{ disabled }}
    >
      <Text style={styles.secondaryLabel}>{label}</Text>
    </Pressable>
  );
}

function TextButton({ label, onPress }: { label: string; onPress: () => void }) {
  return <Pressable style={styles.textButton} onPress={onPress} accessibilityRole="button"><Text style={styles.textButtonLabel}>{label}</Text></Pressable>;
}

function ModeButton({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      style={[styles.modeButton, selected && styles.modeButtonSelected]}
    >
      <Text style={[styles.modeLabel, selected && styles.modeLabelSelected]}>{label}</Text>
    </Pressable>
  );
}

function ChoiceCard({ icon, title, body, selected = false, onPress }: { icon: IconName; title: string; body?: string; selected?: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      style={({ pressed }) => [styles.choiceCard, selected && styles.choiceSelected, pressed && styles.pressed]}
    >
      <Ionicons name={icon} size={24} color={selected ? Colors.primary : Colors.text} />
      <View style={styles.flex}>
        <Text style={styles.cardTitle}>{title}</Text>
        {body ? <Text style={styles.caption}>{body}</Text> : null}
      </View>
      <Ionicons name={selected ? 'checkmark-circle' : 'chevron-forward'} size={20} color={selected ? Colors.primary : Colors.textSecondary} />
    </Pressable>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return <View style={styles.reviewRow}><Text style={styles.caption}>{label}</Text><Text style={styles.reviewValue}>{value}</Text></View>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.lg, paddingBottom: 64, gap: Spacing.md },
  centered: { alignItems: 'center', justifyContent: 'center', padding: Spacing.xl, gap: Spacing.md },
  flex: { flex: 1, minWidth: 0 },
  topRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  eyebrow: { ...Typography.caption, color: Colors.primary, fontWeight: '800', letterSpacing: 1.1 },
  heroTitle: { ...Typography.title, color: Colors.text, fontSize: 30, lineHeight: 35, marginTop: Spacing.sm },
  title: { ...Typography.title, color: Colors.text, textAlign: 'center' },
  body: { ...Typography.body, color: Colors.textSecondary, lineHeight: 21 },
  caption: { ...Typography.caption, color: Colors.textSecondary, lineHeight: 18 },
  sectionLabel: { ...Typography.caption, color: Colors.textSecondary, fontWeight: '800', letterSpacing: 1 },
  deleteText: { ...Typography.caption, color: Colors.textSecondary, fontWeight: '700' },
  choiceCard: { minHeight: 72, borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, padding: Spacing.md, flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  choiceSelected: { borderColor: Colors.primary },
  cardTitle: { ...Typography.body, color: Colors.text, fontWeight: '800' },
  modeRow: { flexDirection: 'row', gap: Spacing.sm },
  modeButton: { minHeight: 44, flex: 1, alignItems: 'center', justifyContent: 'center', borderRadius: Radius.pill, borderWidth: 1, borderColor: Colors.border },
  modeButtonSelected: { borderColor: Colors.primary, backgroundColor: Colors.surface },
  modeLabel: { ...Typography.body, color: Colors.textSecondary, fontWeight: '700' },
  modeLabelSelected: { color: Colors.primary },
  captureStage: { minHeight: 320, borderRadius: Radius.card, backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border, alignItems: 'center', justifyContent: 'center', padding: Spacing.xl, gap: Spacing.md },
  captureTitle: { ...Typography.subtitle, color: Colors.text, fontWeight: '800', textAlign: 'center' },
  primaryButton: { minHeight: 52, borderRadius: Radius.pill, backgroundColor: Colors.primary, alignItems: 'center', justifyContent: 'center', paddingHorizontal: Spacing.lg, marginTop: Spacing.xs },
  primaryLabel: { ...Typography.body, color: Colors.background, fontWeight: '900' },
  secondaryButton: { minHeight: 48, borderRadius: Radius.pill, borderWidth: 1, borderColor: Colors.border, alignItems: 'center', justifyContent: 'center', paddingHorizontal: Spacing.lg },
  secondaryLabel: { ...Typography.body, color: Colors.text, fontWeight: '800' },
  textButton: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  textButtonLabel: { ...Typography.body, color: Colors.textSecondary, fontWeight: '700' },
  pressed: { opacity: 0.78 },
  disabled: { opacity: 0.5 },
  previewImage: { width: '100%', aspectRatio: 4 / 5, borderRadius: Radius.card, backgroundColor: Colors.surface },
  videoPreview: { minHeight: 360, borderRadius: Radius.card, backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border, alignItems: 'center', justifyContent: 'center', gap: Spacing.sm },
  searchRow: { flexDirection: 'row', gap: Spacing.sm },
  searchInput: { minHeight: 50, flex: 1, borderRadius: Radius.pill, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, color: Colors.text, paddingHorizontal: Spacing.md, ...Typography.body },
  searchButton: { width: 50, height: 50, borderRadius: 25, backgroundColor: Colors.primary, alignItems: 'center', justifyContent: 'center' },
  placeRow: { minHeight: 64, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: Colors.border, flexDirection: 'row', alignItems: 'center', gap: Spacing.md, paddingVertical: Spacing.sm },
  selectText: { ...Typography.caption, color: Colors.primary, fontWeight: '800' },
  pendingCard: { borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.primary, backgroundColor: Colors.surface, padding: Spacing.md, flexDirection: 'row', gap: Spacing.sm },
  warning: { borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, padding: Spacing.md, flexDirection: 'row', gap: Spacing.sm },
  warningText: { ...Typography.caption, color: Colors.textSecondary, flex: 1 },
  captionInput: { minHeight: 150, borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, color: Colors.text, padding: Spacing.md, textAlignVertical: 'top', ...Typography.body },
  reviewCard: { borderRadius: Radius.card, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.surface, padding: Spacing.md, gap: Spacing.sm },
  reviewRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: Spacing.md },
  reviewValue: { ...Typography.body, color: Colors.text, fontWeight: '700', flexShrink: 1, textAlign: 'right' },
  privacyNote: { ...Typography.caption, color: Colors.textSecondary, textAlign: 'center', lineHeight: 18 },
  resumeBlock: { marginTop: Spacing.lg, gap: Spacing.sm },
  resumeRow: { minHeight: 58, flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, borderRadius: Radius.card, backgroundColor: Colors.surface, padding: Spacing.md },
  resumeTitle: { ...Typography.body, color: Colors.text, fontWeight: '700' },
});
