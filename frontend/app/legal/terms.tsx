// app/legal/terms.tsx
// See privacy.tsx's header comment -- same reasoning for being in-app.
import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { Colors, Spacing } from '../../src/constants/colors';

const EFFECTIVE_DATE = 'August 25, 2026';

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

export default function TermsOfServiceScreen() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Terms of Service</Text>
      <Text style={styles.updated}>Last updated: {EFFECTIVE_DATE}</Text>

      <P>By creating an account or using CRAVE, you agree to these terms. Please read them.</P>

      <H2>What CRAVE is</H2>
      <P>
        CRAVE helps you discover and rank restaurants using real signals — menus, reviews,
        local coverage, and how people actually eat — and lets you save places, share finds,
        and post short food videos.
      </P>

      <H2>Your account</H2>
      <Li>You're responsible for keeping your account credentials secure.</Li>
      <Li>You must be old enough to use CRAVE under the laws where you live, and at least 13.</Li>
      <Li>One account per person. Don't impersonate someone else or a business you don't represent.</Li>

      <H2>Content you post</H2>
      <P>
        When you save a place, write a review, or post a photo or video, you keep ownership of
        it. By posting, you give CRAVE a license to display, store, and distribute that content
        within the app — that's it, we don't use it anywhere else without asking.
      </P>
      <P>You agree not to post content that:</P>
      <Li>Isn't actually yours to post, or infringes someone else's rights.</Li>
      <Li>Is illegal, harassing, hateful, sexually explicit, or violent.</Li>
      <Li>Is spam, a scam, or deliberately misleading about a place.</Li>
      <Li>Doesn't show real food or a real place — the video feed is for genuine content, not test uploads.</Li>

      <H2>Moderation</H2>
      <P>
        Every photo and video goes through automated screening, and anyone can report content
        that shouldn't be there. Content with enough independent reports is held for human
        review rather than being immediately removed — we'd rather double-check than delete
        something real by mistake. We may remove content or suspend accounts that violate these
        terms.
      </P>

      <H2>Rankings aren't editorial opinion</H2>
      <P>
        CRAVE's place scores and tiers are computed from a blend of signals (menu quality,
        press coverage, user activity, and more) and from rankings CRAVE's own users submit.
        They're a tool for discovery, not a guarantee of quality, and they change as new
        signal comes in.
      </P>

      <H2>No warranty</H2>
      <P>
        CRAVE is provided as-is. We work to keep place information accurate and the app
        running, but we can't guarantee restaurant hours, menus, or availability are current —
        always confirm anything time-sensitive with the restaurant directly.
      </P>

      <H2>Ending your account</H2>
      <P>
        You can delete your account anytime from Settings. We may suspend or remove an account
        that repeatedly violates these terms.
      </P>

      <H2>Changes to these terms</H2>
      <P>If we make a meaningful change, we'll update the date above and let you know in the app.</P>

      <H2>Contact</H2>
      <P>Questions about these terms: hello@crave.app</P>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.xl, paddingBottom: Spacing.xxl * 2 },
  title: { color: Colors.text, fontSize: 26, fontWeight: '800', marginBottom: Spacing.xs },
  updated: { color: Colors.textMuted, fontSize: 13, marginBottom: Spacing.xl },
  h2: { color: Colors.text, fontSize: 17, fontWeight: '700', marginTop: Spacing.xl, marginBottom: Spacing.sm },
  p: { color: Colors.textSecondary, fontSize: 14.5, lineHeight: 21, marginBottom: Spacing.sm },
  li: { flexDirection: 'row', marginBottom: Spacing.sm, paddingRight: Spacing.xs },
  liBullet: { color: Colors.primary, fontSize: 14.5, marginRight: Spacing.sm, lineHeight: 21 },
  liText: { flex: 1, color: Colors.textSecondary, fontSize: 14.5, lineHeight: 21 },
});
