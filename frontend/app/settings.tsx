import React, { useState } from 'react';
import {
  Alert, Linking, ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Application from 'expo-application';
import * as Haptics from 'expo-haptics';
import { useRouter, useFocusEffect } from 'expo-router';
import { Colors, Spacing, Radius } from '../src/constants/colors';
import { useCityStore } from '../src/stores/cityStore';
import { useAuthStore } from '../src/stores/authStore';
import { useToast } from '../src/hooks/useToast';
import { deleteMyAccount } from '../src/api/social';
import {
  getPushPermissionStatus,
  requestAndRegisterPush,
  PushPermissionStatus,
} from '../src/services/pushNotifications';

const APP_VERSION = Application.nativeApplicationVersion ?? 'Development';
const BUILD_VERSION = Application.nativeBuildVersion;
const VERSION_LABEL = BUILD_VERSION ? `${APP_VERSION} (${BUILD_VERSION})` : APP_VERSION;

interface RowProps {
  icon: React.ComponentProps<typeof Ionicons>['name'];
  label: string;
  sublabel?: string;
  onPress?: () => void;
  rightEl?: React.ReactNode;
  tint?: string;
}

function Row({ icon, label, sublabel, onPress, rightEl, tint }: RowProps) {
  const content = (
    <View style={styles.row}>
      <View style={[styles.rowIcon, tint ? { backgroundColor: tint + '22' } : null]}>
        <Ionicons name={icon} size={18} color={tint ?? Colors.textSecondary} />
      </View>
      <View style={styles.rowBody}>
        <Text style={[styles.rowLabel, tint ? { color: tint } : null]}>{label}</Text>
        {sublabel ? <Text style={styles.rowSub}>{sublabel}</Text> : null}
      </View>
      {rightEl ?? (
        onPress ? <Ionicons name="chevron-forward" size={16} color={Colors.textSecondary} /> : null
      )}
    </View>
  );

  if (!onPress) return content;
  return (
    <TouchableOpacity
      onPress={() => {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        onPress();
      }}
      activeOpacity={0.75}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      {content}
    </TouchableOpacity>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <Text style={styles.sectionTitle}>{title}</Text>;
}

function Divider() {
  return <View style={styles.divider} />;
}

const NOTIFICATION_STATUS_COPY: Record<PushPermissionStatus, string> = {
  granted: 'Enabled — tap to manage in Settings',
  denied: 'Off — tap to open Settings',
  undetermined: 'Off — tap to turn on',
  unavailable: 'Not available on this build',
};

export default function MoreScreen() {
  const router = useRouter();
  const selectedCity = useCityStore((s) => s.selectedCity);
  const user = useAuthStore((s) => s.user);
  const signOut = useAuthStore((s) => s.signOut);
  const toast = useToast((s) => s.show);
  const [notificationStatus, setNotificationStatus] = useState<PushPermissionStatus>('undetermined');

  useFocusEffect(
    React.useCallback(() => {
      let cancelled = false;
      getPushPermissionStatus().then((status) => {
        if (!cancelled) setNotificationStatus(status);
      });
      return () => {
        cancelled = true;
      };
    }, []),
  );

  const handleNotificationsPress = () => {
    if (notificationStatus === 'unavailable') return;
    if (notificationStatus === 'granted' || notificationStatus === 'denied') {
      Linking.openSettings().catch(() => toast("Couldn't open Settings."));
      return;
    }
    Alert.alert(
      'Enable notifications',
      "Get notified when your photo or video submission is approved or rejected.",
      [
        { text: 'Not now', style: 'cancel' },
        {
          text: 'Enable',
          onPress: async () => {
            const result = await requestAndRegisterPush();
            setNotificationStatus(result);
          },
        },
      ],
    );
  };

  const handleSignOut = () => {
    Alert.alert('Sign out?', "You'll need to sign back in to rank places or see your Craves.", [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive', onPress: () => signOut() },
    ]);
  };

  const handleDeleteAccount = () => {
    Alert.alert(
      'Delete your account?',
      'This permanently deletes your account, personal activity, saves, rankings, reports, and uploaded photos/videos. It cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete Account',
          style: 'destructive',
          onPress: () => {
            Alert.alert('Are you absolutely sure?', 'This cannot be undone.', [
              { text: 'Cancel', style: 'cancel' },
              {
                text: 'Yes, delete everything',
                style: 'destructive',
                onPress: async () => {
                  try {
                    await deleteMyAccount();
                  } catch {
                    toast("Couldn't complete account deletion. Your session is still active — try again.");
                    return;
                  }
                  await signOut();
                },
              },
            ]);
          },
        },
      ],
    );
  };

  const openLink = (url: string) => {
    Linking.openURL(url).catch(() => toast("Couldn't open that link."));
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.wordmark}>CRAVE</Text>
        <Text style={styles.tagline}>Your cultural discovery engine</Text>
      </View>

      <SectionTitle title="CITY" />
      <View style={styles.card}>
        <View style={styles.row}>
          <View style={styles.rowIcon}>
            <Ionicons name="location-outline" size={18} color={Colors.textSecondary} />
          </View>
          <View style={styles.rowBody}>
            <Text style={styles.rowLabel}>Current City</Text>
            <Text style={styles.rowSub}>{selectedCity?.name ?? 'None selected'}</Text>
          </View>
        </View>
        <Divider />
        <Row
          icon="add-circle-outline"
          label="Add a new spot"
          sublabel="Found somewhere CRAVE doesn't have yet?"
          tint={Colors.primary}
          onPress={() => router.push('/add-spot')}
        />
      </View>

      <SectionTitle title="APP" />
      <View style={styles.card}>
        <Row
          icon="notifications-outline"
          label="Notifications"
          sublabel={NOTIFICATION_STATUS_COPY[notificationStatus]}
          tint={notificationStatus === 'unavailable' ? Colors.textMuted : undefined}
          onPress={notificationStatus === 'unavailable' ? undefined : handleNotificationsPress}
        />
        <Divider />
        <Row
          icon="star-outline"
          label="Rate CRAVE"
          sublabel="Coming soon"
          tint={Colors.textMuted}
        />
      </View>

      <SectionTitle title="ABOUT" />
      <View style={styles.card}>
        <Row
          icon="information-circle-outline"
          label="How CRAVE Works"
          sublabel="Our discovery engine explained"
          onPress={() =>
            Alert.alert(
              'How CRAVE Works',
              "CRAVE ranks restaurants from real signals — menus, reviews, " +
                'local blogs, and how people actually eat — instead of paid ' +
                'placements. The S/A/B/C tier badge reflects that blended ' +
                'score. See a place on social media? Share it to CRAVE and ' +
                "it'll show up in your Craves, matched to the real place " +
                'automatically.',
            )
          }
        />
        <Divider />
        <Row
          icon="shield-checkmark-outline"
          label="Privacy Policy"
          onPress={() => router.push('/legal/privacy')}
        />
        <Divider />
        <Row
          icon="document-text-outline"
          label="Terms of Service"
          onPress={() => router.push('/legal/terms')}
        />
        <Divider />
        <Row
          icon="code-slash-outline"
          label="Version"
          rightEl={<Text style={styles.version}>{VERSION_LABEL}</Text>}
        />
      </View>

      <SectionTitle title="SUPPORT" />
      <View style={styles.card}>
        <Row
          icon="chatbubble-outline"
          label="Send Feedback"
          sublabel="Help us improve CRAVE"
          onPress={() => openLink('mailto:hello@crave.app?subject=CRAVE Feedback')}
        />
      </View>

      {user ? (
        <>
          <SectionTitle title="ACCOUNT" />
          <View style={styles.card}>
            <Row
              icon="person-outline"
              label={user.email ?? 'Signed in'}
              sublabel="Your CRAVE account"
            />
            <Divider />
            <Row
              icon="log-out-outline"
              label="Sign Out"
              tint={Colors.error}
              onPress={handleSignOut}
            />
            <Divider />
            <Row
              icon="trash-outline"
              label="Delete Account"
              sublabel="Permanently delete your account and associated data"
              tint={Colors.error}
              onPress={handleDeleteAccount}
            />
          </View>
        </>
      ) : null}

      <Text style={styles.footer}>Made with taste.</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { paddingBottom: 48 },
  header: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.lg,
  },
  wordmark: {
    fontSize: 26,
    fontWeight: '900',
    color: Colors.primary,
    letterSpacing: 3,
  },
  tagline: {
    fontSize: 13,
    color: Colors.textSecondary,
    fontWeight: '500',
    marginTop: Spacing.xs,
  },
  sectionTitle: {
    fontSize: 10,
    fontWeight: '800',
    color: Colors.textSecondary,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  card: {
    marginHorizontal: Spacing.lg,
    backgroundColor: Colors.surface,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.border,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    gap: Spacing.md,
    minHeight: 56,
  },
  rowIcon: {
    width: 32,
    height: 32,
    borderRadius: Radius.sm,
    backgroundColor: Colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowBody: { flex: 1, gap: Spacing.xs },
  rowLabel: { fontSize: 15, fontWeight: '600', color: Colors.text },
  rowSub: { fontSize: 12, color: Colors.textSecondary },
  divider: { height: 1, backgroundColor: Colors.border, marginLeft: 56 },
  version: { fontSize: 13, color: Colors.textSecondary, fontWeight: '500' },
  footer: {
    textAlign: 'center',
    color: Colors.textSecondary,
    fontSize: 12,
    fontWeight: '500',
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.sm,
  },
});
