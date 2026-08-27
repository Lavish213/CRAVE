// app/+not-found.tsx
//
// Expo Router's catch-all for any URL/deep-link that doesn't match a route
// (e.g. a stale crave://place/<id> link, a malformed share link, or a typo'd
// path). Without this file, Expo Router falls back to its own generic
// "Unmatched Route" screen — plain white background, default system font,
// completely off-brand, and with no way back into the app.
import { Link, Stack } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing } from '../src/constants/colors';

export default function NotFoundScreen() {
  return (
    <>
      <Stack.Screen options={{ title: 'Not Found' }} />
      <View style={styles.container}>
        <Ionicons name="compass-outline" size={44} color={Colors.textSecondary} />
        <Text style={styles.title}>This page doesn't exist</Text>
        <Text style={styles.body}>
          The link you followed may be broken, or the page may have moved.
        </Text>
        <Link href="/" style={styles.link}>
          <Text style={styles.linkText}>Back to CRAVE</Text>
        </Link>
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    paddingHorizontal: 32,
    backgroundColor: Colors.background,
  },
  title: { color: Colors.text, fontSize: 18, fontWeight: '700', textAlign: 'center' },
  body: { color: Colors.textSecondary, fontSize: 14, textAlign: 'center', lineHeight: 20 },
  link: {
    marginTop: Spacing.md,
    paddingHorizontal: 22,
    paddingVertical: 11,
    borderRadius: 22,
    backgroundColor: Colors.primary,
  },
  linkText: { color: '#FFFFFF', fontSize: 14, fontWeight: '700' },
});
