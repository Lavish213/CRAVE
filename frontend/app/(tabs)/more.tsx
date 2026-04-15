import React from 'react';
import {
  Linking, ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { Colors, Spacing, Radius } from '../../src/constants/colors';
import { useCityStore } from '../../src/stores/cityStore';

// App version — hardcoded, update for each release
const APP_VERSION = '1.0.0';

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
        onPress ? <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} /> : null
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

export default function MoreScreen() {
  const selectedCity = useCityStore((s) => s.selectedCity);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.wordmark}>CRAVE</Text>
        <Text style={styles.tagline}>Your cultural discovery engine</Text>
      </View>

      {/* City */}
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
      </View>

      {/* App */}
      <SectionTitle title="APP" />
      <View style={styles.card}>
        <Row
          icon="notifications-outline"
          label="Notifications"
          sublabel="Coming soon"
          tint={Colors.textMuted}
        />
        <Divider />
        <Row
          icon="star-outline"
          label="Rate CRAVE"
          sublabel="Tell us what you think"
          onPress={() => { /* App Store link placeholder */ }}
        />
      </View>

      {/* About */}
      <SectionTitle title="ABOUT" />
      <View style={styles.card}>
        <Row
          icon="information-circle-outline"
          label="How CRAVE Works"
          sublabel="Our discovery engine explained"
          onPress={() => { /* onboarding modal placeholder */ }}
        />
        <Divider />
        <Row
          icon="shield-checkmark-outline"
          label="Privacy Policy"
          onPress={() => Linking.openURL('https://crave.app/privacy')}
        />
        <Divider />
        <Row
          icon="document-text-outline"
          label="Terms of Service"
          onPress={() => Linking.openURL('https://crave.app/terms')}
        />
        <Divider />
        <Row
          icon="code-slash-outline"
          label="Version"
          rightEl={<Text style={styles.version}>{APP_VERSION}</Text>}
        />
      </View>

      {/* Support */}
      <SectionTitle title="SUPPORT" />
      <View style={styles.card}>
        <Row
          icon="chatbubble-outline"
          label="Send Feedback"
          sublabel="Help us improve CRAVE"
          onPress={() => Linking.openURL('mailto:hello@crave.app?subject=CRAVE Feedback')}
        />
      </View>

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
    color: Colors.textMuted,
    fontWeight: '500',
    marginTop: Spacing.xs,
  },
  sectionTitle: {
    fontSize: 10,
    fontWeight: '800',
    color: Colors.textMuted,
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
  rowBody: { flex: 1 },
  rowLabel: { fontSize: 15, fontWeight: '600', color: Colors.text },
  rowSub: { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  divider: { height: 1, backgroundColor: Colors.border, marginLeft: 56 },
  version: { fontSize: 13, color: Colors.textMuted, fontWeight: '500' },
  footer: {
    textAlign: 'center',
    color: Colors.textMuted,
    fontSize: 12,
    fontWeight: '500',
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.sm,
  },
});
