// Web-only override for the Map tab, picked up automatically by Metro's
// platform-extension resolution (map.web.tsx wins over map.tsx when
// bundling for web) — see map.tsx's sibling for why this file needs to
// exist at all: `react-native-maps` imports React Native internals
// (codegenNativeCommands) that don't exist on web, and Metro fails that
// import at bundle time, not at runtime. Because expo-router's file-based
// routing scans every file under app/ (via require.context) to build its
// route table, that single failure previously took down the ENTIRE web
// bundle — every tab, not just this one — since Metro won't serve a bundle
// that failed to build at all. This stub keeps the route wired up without
// ever importing react-native-maps, so the rest of the app (which has no
// other web-incompatible imports) can actually build and render on web.
import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing } from '../../src/constants/colors';

export default function MapScreenWebFallback() {
  return (
    <View style={styles.container}>
      <Ionicons name="map-outline" size={40} color={Colors.textSecondary} />
      <Text style={styles.title}>Map isn't available in the browser preview</Text>
      <Text style={styles.body}>
        Open CRAVE on iOS or Android to see the map — this tab needs native
        map support the web preview can't provide.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.xl,
    backgroundColor: Colors.background,
    gap: Spacing.sm,
  },
  title: { fontSize: 16, fontWeight: '700', color: Colors.text, textAlign: 'center' },
  body: { fontSize: 14, color: Colors.textSecondary, textAlign: 'center', lineHeight: 20 },
});
