import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { Colors, Radius, Spacing, Typography } from '../src/constants/colors';

type CaptureKind = 'photo' | 'video';

type SelectedMedia = {
  kind: CaptureKind;
  uri: string;
};

export default function FoodEvidenceScreen() {
  const router = useRouter();
  const [selectedMedia, setSelectedMedia] = useState<SelectedMedia | null>(null);

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
      setSelectedMedia({ kind: 'photo', uri: result.assets[0].uri });
    }
  }

  async function chooseFromLibrary(kind: CaptureKind) {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: kind === 'photo' ? ['images'] : ['videos'],
      allowsEditing: false,
      quality: kind === 'photo' ? 0.9 : 1,
    });

    if (!result.canceled && result.assets[0]?.uri) {
      setSelectedMedia({ kind, uri: result.assets[0].uri });
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
        <CaptureButton icon="camera-outline" label="Take Photo" onPress={() => void takePhoto()} />
        <CaptureButton icon="images-outline" label="Choose Photo" onPress={() => void chooseFromLibrary('photo')} />
        <CaptureButton icon="videocam-outline" label="Choose Video" onPress={() => void chooseFromLibrary('video')} />
      </View>

      {selectedMedia ? (
        <View style={styles.selectedCard}>
          <Ionicons
            name={selectedMedia.kind === 'photo' ? 'image-outline' : 'videocam-outline'}
            size={22}
            color={Colors.primary}
          />
          <View style={styles.selectedCopy}>
            <Text style={styles.selectedTitle}>
              {selectedMedia.kind === 'photo' ? 'Photo selected' : 'Video selected'}
            </Text>
            <Text style={styles.selectedBody} numberOfLines={1}>
              Media is ready for restaurant identification.
            </Text>
          </View>
          <Pressable
            onPress={() => router.push('/add-spot')}
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
}: {
  icon: React.ComponentProps<typeof Ionicons>['name'];
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [styles.captureButton, pressed && styles.pressed]}
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
