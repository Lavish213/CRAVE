// app/legal/privacy.tsx
//
// In-app privacy policy. App Store Connect / Google Play still require a
// real hosted privacy-policy URL; this screen is the in-app source of truth,
// not a substitute for those store-console fields.
import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { Colors, Spacing } from '../../src/constants/colors';

const EFFECTIVE_DATE = 'September 6, 2026';

function H2({ children }: { children: React.ReactNode }) {
  return <Text style={styles.h2}>{children}</Text>;
}

function P({ children }: { children: React.ReactNode }) {
  return <Text style={styles.p}>{children}</Text>;
}

function Li({ children }: { children: React.ReactNode }) {
  return (
    <View style={styles.li}>
      <Text style={styles.liBullet}>{'•'}</Text>
      <Text style={styles.liText}>{children}</Text>
    </View>
  );
}

export default function PrivacyPolicyScreen() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Privacy Policy</Text>
      <Text style={styles.updated}>Last updated: {EFFECTIVE_DATE}</Text>

      <P>
        This policy explains what CRAVE collects, why, and what control you have over it.
        We don't sell your data, and we don't run ads or ad-tracking of any kind.
      </P>

      <H2>What we collect</H2>
      <Li><Text style={styles.bold}>Account info:</Text> your email address and, if you set them, a username, display name, avatar, and bio.</Li>
      <Li><Text style={styles.bold}>Location:</Text> your device's location, only while the app is in use, to show nearby places and personalize the map. You can deny or revoke this anytime in your device settings — CRAVE still works, just without location-based results.</Li>
      <Li><Text style={styles.bold}>Photos &amp; videos:</Text> images or short videos you choose to upload of food or menus, and the camera/microphone access needed to record them. We only access the camera/mic when you're actively recording.</Li>
      <Li><Text style={styles.bold}>Content you create:</Text> places you save, rankings and comparisons you make, accounts you follow, reports you file, and links you share into the app.</Li>
      <Li><Text style={styles.bold}>Push notification token:</Text> if you allow notifications, a device token used only to tell you about your own uploads (for example, that a submission was approved or rejected).</Li>
      <Li><Text style={styles.bold}>Operational logs:</Text> our backend and hosting providers may process basic request and error metadata needed to operate, secure, and troubleshoot the service. CRAVE does not currently use a separate in-app crash-reporting SDK.</Li>

      <H2>Who we share it with</H2>
      <P>We use a small number of service providers to run CRAVE. Each only receives what it needs to do its job:</P>
      <Li><Text style={styles.bold}>Supabase</Text> — handles sign-in and issues your account session.</Li>
      <Li><Text style={styles.bold}>Cloudflare R2</Text> — stores the photos and videos you upload.</Li>
      <Li><Text style={styles.bold}>Railway</Text> — hosts our backend and database.</Li>
      <Li><Text style={styles.bold}>Google Places API</Text> — looks up restaurant details and photos; we send place queries, not your personal account profile.</Li>
      <Li><Text style={styles.bold}>Expo's push notification service</Text> — delivers notifications when you enable them.</Li>
      <P>We do not sell personal data to anyone, and we do not share it with advertisers.</P>

      <H2>Your controls</H2>
      <Li>Edit or remove your profile info from your account.</Li>
      <Li>Delete your account from Settings. A completed deletion removes the account, personal activity and saved data associated with it, reports you filed, and user-uploaded photos/videos. If deletion cannot complete, the app reports the failure instead of signing you out as though it succeeded.</Li>
      <Li>Turn location or notification permissions off anytime in your device's system settings.</Li>
      <Li>Request a copy of your data, or ask a question about this policy, using Send Feedback in Settings.</Li>

      <H2>Data retention</H2>
      <P>
        CRAVE does not intentionally retain personal account data after a completed account-deletion request unless retention is required for a legitimate legal, security, fraud-prevention, or regulatory reason. Public restaurant facts that no longer identify or reference the deleted account may remain as part of the restaurant catalog.
      </P>

      <H2>Children</H2>
      <P>CRAVE isn't directed at children under 13, and we don't knowingly collect data from them.</P>

      <H2>Changes to this policy</H2>
      <P>If this policy changes in a meaningful way, we'll update the date above and, for significant changes, let you know in the app.</P>

      <H2>Contact</H2>
      <P>Questions about this policy or your data: hello@crave.app</P>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.xl, paddingBottom: Spacing.xxl * 2 },
  title: { color: Colors.text, fontSize: 26, fontWeight: '800', marginBottom: Spacing.xs },
  updated: { color: Colors.textSecondary, fontSize: 13, marginBottom: Spacing.xl },
  h2: { color: Colors.text, fontSize: 17, fontWeight: '700', marginTop: Spacing.xl, marginBottom: Spacing.sm },
  p: { color: Colors.textSecondary, fontSize: 14.5, lineHeight: 21, marginBottom: Spacing.sm },
  bold: { color: Colors.text, fontWeight: '700' },
  li: { flexDirection: 'row', marginBottom: Spacing.sm, paddingRight: Spacing.xs },
  liBullet: { color: Colors.primary, fontSize: 14.5, marginRight: Spacing.sm, lineHeight: 21 },
  liText: { flex: 1, color: Colors.textSecondary, fontSize: 14.5, lineHeight: 21 },
});
