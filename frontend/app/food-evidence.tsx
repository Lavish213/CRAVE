import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { Colors, Radius, Spacing, Typography } from '../src/constants/colors';
import { useAuthStore } from '../src/stores/authStore';
import { AuthSheet } from '../src/components/AuthSheet';
import { usePostingDraftStore } from '../src/stores/postingDraftStore';
import { useToast } from '../src/hooks/useToast';

type CaptureKind = 'photo' | 'video';

type SelectedMedia = {
  kind: CaptureKind;
  uri: string;
  fileSize?: number;
  mimeType?: string;
};

export default function FoodEvidenceScreen() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const toast = useToast((s) => s.show);
  const createDraftFromCapture = usePostingDraftStore((s) => s.createDraftFromCapture);

  const [selectedMedia, setSelectedMedia] = useState<SelectedMedia | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [authVisible, setAuthVisible] = useState(false);

  // A draft needs an owner the moment it's created (durable persistence +
  // account-scoped resolution both depend on it), so this is checked once
  // up front rather than only once the user hits Continue -- previously
  // this screen had no sign-in gate at all, and an anonymous capture would
  // only hit a wall on add-spot.tsx's own gate, after the effort of
  // capturing was already spent.
  if (!user) {
    return (
      <View style={[styles.container, styles.centered]}>
        <Ionicons name="person-circle-outline" size={44} color={Colors.textSecondary} />
        <Text style={styles.emptyTitle}>Sign in to record food evidence</Text>
        <Text style={styles.emptyBody}>Your capture is saved to your own account, not shared until you decide.</Text>
        <Pressable
          onPress={() => setAuthVisible(true)}
          accessibilityRole="button"
          accessibilityLabel="Sign in"
          style={styles.continueButton}
        >
          <Text style={styles.continueLabel}>Sign in</Text>
        </Pressable>
        <AuthSheet visible={authVisible} onClose={() => setAuthVisible(false)} reason="default" />
      </View>
    );
  }

  // Immediately persists the captured media into a durable, app-owned
  // PostingDraft -- before any restaurant identification, upload, or
  // navigation. Previously this screen only held media in local component
  // state, which the "Continue" press then had to carry along as route
  // params; either way, anything short of finishing the flow in one go
  // (backgrounding, a crash, the OS reclaiming memory) lost the capture
  // entirely. The draft survives all of that.
  async function persistCapture(kind: CaptureKind, asset: { uri: string; fileSize?: number; mimeType?: string }) {
    setSaving(true);
    try {
      const draft = await createDraftFromCapture({
        ownerId: user!.id,
        sourceUri: asset.uri,
        kind,
        mimeType: asset.mimeType,
        fileSize: asset.fileSize,
      });
      setDraftId(draft.id);
      setSelectedMedia({ kind, uri: draft.localUri, fileSize: asset.fileSize, mimeType: asset.mimeType });
    } catch (err) {
      toast(err instanceof Error ? err.message : "Couldn't save that capture");
    } finally {
      setSaving(false);
    }
  }

  async function takePhoto() {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Camera unavailable', 'Choose a photo or video from your library instead.');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ['images'],
      allowsEditing: false,
      quality: 0.9,
    });

    if (!result.canceled && result.assets[0]?.uri) {
      const asset = result.assets[0];
      await persistCapture('photo', { uri: asset.uri, fileSize: asset.fileSize, mimeType: asset.mimeType });
    }
  }

  async function chooseFromLibrary(kind: CaptureKind) {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: kind === 'photo' ? ['images'] : ['videos'],
      allowsEditing: false,
      quality: kind === 'photo' ? 0.9 : 1,
    });

    if (!result.canceled && result.assets[0]?.uri) {
      const asset = result.assets[0];
      await persistCapture(kind, { uri: asset.uri, fileSize: asset.fileSize, mimeType: asset.mimeType });
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.eyebrow}>RECORD FOOD EVIDENCE</Text>
        <Text style={styles.title}>What did you eat?</Text>
        <Text style={styles.body}>
          Start with media. Restaurant identification and the private-or-post decision come next.
        </Text>
      </View>

      <View style={styles.actions}>
        <CaptureButton icon="camera-outline" label="Take Photo" onPress={() => void takePhoto()} disabled={saving} />
        <CaptureButton icon="images-outline" label="Choose Photo" onPress={() => void chooseFromLibrary('photo')} disabled={saving} />
        <CaptureButton icon="videocam-outline" label="Choose Video" onPress={() => void chooseFromLibrary('video')} disabled={saving} />
      </View>

      {selectedMedia && draftId ? (
        <View style={styles.selectedCard}>
          <Ionicons
            name={selectedMedia.kind === 'photo' ? 'image-outline' : 'videocam-outline'}
            size={22}
            color={Colors.primary}
          />
          <View style={styles.selectedCopy}>
            <Text style={styles.selectedTitle}>
              {selectedMedia.kind === 'photo' ? 'Photo saved' : 'Video saved'}
            </Text>
            <Text style={styles.selectedBody} numberOfLines={1}>
              Ready for restaurant identification.
            </Text>
          </View>
          <Pressable
            onPress={() => router.push({ pathname: '/add-spot', params: { draftId } })}
            accessibilityRole="button"
            accessibilityLabel="Identify restaurant"
            style={styles.continueButton}
          >
            <Text style={styles.continueLabel}>Continue</Text>
          </Pressable>
        </View>
      ) : null}

      <Text style={styles.privacyNote}>
        Nothing is published from this step. Visibility is chosen explicitly later.
      </Text>
    </View>
  );
}

function CaptureButton({
  icon,
  label,
  onPress,
  disabled,
}: {
  icon: React.ComponentProps<typeof Ionicons>['name'];
  label: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [styles.captureButton, pressed && styles.pressed, disabled && styles.captureButtonDisabled]}
    >
      <Ionicons name={icon} size={24} color={Colors.text} />
      <Text style={styles.captureLabel}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
    padding: Spacing.lg,
  },
  centered: { alignItems: 'center', justifyContent: 'center', gap: Spacing.sm },
  emptyTitle: { color: Colors.text, fontSize: 18, fontWeight: '700', textAlign: 'center' },
  emptyBody: { color: Colors.textSecondary, fontSize: 14, textAlign: 'center' },
  header: { marginTop: Spacing.sm, marginBottom: Spacing.xl },
  eyebrow: {
    ...Typography.caption,
    color: Colors.primary,
    fontWeight: '800',
    letterSpacing: 1.1,
    marginBottom: Spacing.xs,
  },
  title: { ...Typography.title, color: Colors.text, marginBottom: Spacing.sm },
  body: { ...Typography.body, color: Colors.textSecondary, maxWidth: 520 },
  actions: { gap: Spacing.sm },
  captureButton: {
    minHeight: 58,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingHorizontal: Spacing.lg,
  },
  captureButtonDisabled: { opacity: 0.5 },
  captureLabel: { ...Typography.body, color: Colors.text, fontWeight: '700' },
  pressed: { opacity: 0.82 },
  selectedCard: {
    marginTop: Spacing.xl,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  selectedCopy: { flex: 1, minWidth: 0 },
  selectedTitle: { ...Typography.body, color: Colors.text, fontWeight: '700' },
  selectedBody: { ...Typography.caption, color: Colors.textSecondary, marginTop: 2 },
  continueButton: {
    minHeight: 44,
    paddingHorizontal: Spacing.md,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary,
  },
  continueLabel: { ...Typography.body, color: Colors.background, fontWeight: '800' },
  privacyNote: {
    ...Typography.caption,
    color: Colors.textSecondary,
    marginTop: Spacing.lg,
    textAlign: 'center',
  },
});
