import { useEffect, Component, ReactNode } from 'react';
import { AppState, Platform, View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Stack, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import * as Notifications from 'expo-notifications';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '../src/lib/queryClient';
import { useCityStore } from '../src/stores/cityStore';
import { useAuthStore } from '../src/stores/authStore';
import { useCravesStore } from '../src/stores/cravesStore';
import { useVideoQueueStore, setActiveUserForVideoSync } from '../src/stores/videoQueueStore';
import { usePushNotifications } from '../src/hooks/usePushNotifications';
import { pingStreak } from '../src/api/streak';
import { isSupabaseConfigured } from '../src/lib/supabase';
import { Colors, Spacing } from '../src/constants/colors';
import { ToastContainer } from '../src/components/Toast';

// Without an explicit handler, expo-notifications silently drops a
// notification that arrives while the app is in the foreground -- it
// only shows automatically when backgrounded/killed. CRAVE's push
// notifications (video approved/rejected) are exactly the kind of thing
// a user might trigger themselves by re-opening the app right after
// recording, so showing them in-app matters as much as in the tray.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) {
      return (
        <View style={eb.container}>
          <Text style={eb.title}>Something went wrong</Text>
          <Text style={eb.body}>CRAVE hit an unexpected error.</Text>
          <TouchableOpacity style={eb.btn} onPress={() => this.setState({ hasError: false })}>
            <Text style={eb.btnText}>Try again</Text>
          </TouchableOpacity>
        </View>
      );
    }
    return this.props.children;
  }
}

const eb = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.background, padding: Spacing.xl },
  title: { fontSize: 20, fontWeight: '800', color: Colors.text, marginBottom: Spacing.sm },
  body: { fontSize: 14, color: Colors.textSecondary, textAlign: 'center', marginBottom: Spacing.lg },
  btn: { backgroundColor: Colors.primary, paddingHorizontal: Spacing.lg, paddingVertical: Spacing.sm, borderRadius: 8 },
  btnText: { color: Colors.text, fontWeight: '700', fontSize: 14 },
});

// Shown instead of the app when EXPO_PUBLIC_SUPABASE_URL/ANON_KEY are
// missing -- a developer/build-config problem, not something a real user
// can hit in a correctly configured build. Deliberately plain-language and
// specific (names the exact env vars and where to set them) since this
// replaces what used to be an opaque module-load-time crash.
function ConfigErrorScreen() {
  return (
    <View style={eb.container}>
      <Text style={eb.title}>Configuration error</Text>
      <Text style={eb.body}>
        CRAVE can't start: EXPO_PUBLIC_SUPABASE_URL and/or
        EXPO_PUBLIC_SUPABASE_ANON_KEY are missing. Copy frontend/.env.example
        to frontend/.env, fill in real values from the Supabase project
        dashboard, and restart the dev server (or rebuild).
      </Text>
    </View>
  );
}

export default function RootLayout() {
  const router = useRouter();
  const initCities = useCityStore((s) => s.initCities);
  const initAuth = useAuthStore((s) => s.init);
  const user = useAuthStore((s) => s.user);
  const loadSaves = useCravesStore((s) => s.loadSaves);
  const runVideoSyncPass = useVideoQueueStore((s) => s.runSyncPass);

  usePushNotifications(user?.id);

  // Routes a tapped moderation-outcome notification to the relevant
  // place, when one is known -- "video_approved"/"photo_approved" carry
  // a placeId (see video_processing_worker.py / moderation.py), rejection
  // notifications don't (nowhere specific to route a rejection to).
  // Previously nothing handled a tap at all -- it just opened the app to
  // wherever it already was.
  useEffect(() => {
    // expo-notifications doesn't implement getLastNotificationResponseAsync()
    // on web (push notifications aren't a concept there at all -- see
    // usePushNotifications.ts's own currentPlatform() gate) -- calling it
    // threw and broke the entire web build, found by the Playwright E2E
    // smoke suite.
    if (Platform.OS === 'web') return;

    function routeFromNotificationData(data: Record<string, unknown> | undefined) {
      const placeId = data?.placeId;
      if (typeof placeId === 'string' && placeId) {
        router.push(`/place/${placeId}`);
      }
    }

    // Cold-start case: the app was launched *by* tapping a notification --
    // addNotificationResponseReceivedListener below only fires for a tap
    // that happens while already running.
    Notifications.getLastNotificationResponseAsync().then((response) => {
      if (response) {
        routeFromNotificationData(response.notification.request.content.data as Record<string, unknown>);
      }
    });

    const subscription = Notifications.addNotificationResponseReceivedListener((response) => {
      routeFromNotificationData(response.notification.request.content.data as Record<string, unknown>);
    });
    return () => subscription.remove();
  }, [router]);

  useEffect(() => {
    initAuth();
    initCities();
  }, []);

  // When user becomes known (login or session restore), sync saves from backend
  useEffect(() => {
    if (user?.id) {
      loadSaves(user.id);
    }
  }, [user?.id, loadSaves]);

  // Registers which account owns any offline-queued videos for
  // videoQueueStore's own AppState-foreground listener (see that store's
  // setActiveUserForVideoSync doc comment for why this can't infer it on
  // its own), and drains anything already queued right now -- not just on
  // the next foreground event, so a video recorded in a previous session
  // doesn't wait for one more background/foreground cycle to start
  // syncing.
  useEffect(() => {
    setActiveUserForVideoSync(user?.id ?? null);
    if (user?.id) {
      runVideoSyncPass(user.id).catch(() => {});
    }
  }, [user?.id, runVideoSyncPass]);

  // Streak gamification: what counts as a "streak day" is still an open
  // product decision (see streak_service.py's module docstring), so this
  // pings on the loosest possible trigger for now -- any time the app is
  // opened or returns to the foreground while signed in. Ping is
  // idempotent server-side for the same calendar day, and best-effort:
  // a failure here should never be user-visible.
  useEffect(() => {
    if (!user?.id) return;
    pingStreak().catch(() => {});
    const subscription = AppState.addEventListener('change', (nextState) => {
      if (nextState === 'active') {
        pingStreak().catch(() => {});
      }
    });
    return () => subscription.remove();
  }, [user?.id]);

  if (!isSupabaseConfigured) {
    return <ConfigErrorScreen />;
  }

  return (
    <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <View style={{ flex: 1, backgroundColor: Colors.background }}>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: Colors.background },
            headerTintColor: '#FFFFFF',
            headerTitleStyle: { fontWeight: '700' },
            contentStyle: { backgroundColor: Colors.background },
          }}
        >
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          {/* A true shared-element transition (the card's photo morphing
              into the hero image) was researched and deliberately skipped:
              react-native-reanimated's shared-element API has documented
              crash reports specifically with expo-router (nested-stack and
              Android back-navigation), needs an explicit opt-in flag on
              Reanimated 4 (what this app runs), and there's no confirmed
              crash monitoring live yet to catch it if it misbehaves for a
              slice of users. `fade_from_bottom` is the safe middle ground —
              fully supported by native-stack, no native risk — for the two
              screens that are the actual product moments (opening a place,
              starting to rank it) rather than the default slide-from-right
              every push gets. */}
          {/* Full-screen camera UI with its own close button -- a native
              header here would show the raw "record-video" route name
              stacked above a screen that already has its own close
              affordance, not just a bad title. */}
          <Stack.Screen name="record-video/[placeId]" options={{ headerShown: false }} />
          <Stack.Screen name="place/[id]" options={{ title: '', animation: 'fade_from_bottom' }} />
          <Stack.Screen name="rank/[placeId]" options={{ title: 'Rank this place', animation: 'fade_from_bottom' }} />
          <Stack.Screen name="user/[id]" options={{ title: '' }} />
          <Stack.Screen name="profile-setup" options={{ title: 'Set up profile' }} />
          {/* No title override previously -- expo-router falls back to the
              raw route name, so this screen's header literally read
              "add-spot" instead of a real title. */}
          <Stack.Screen name="add-spot" options={{ title: 'Add a Spot' }} />
          <Stack.Screen name="friends-feed" options={{ title: 'Friends' }} />
          <Stack.Screen name="leaderboard" options={{ title: 'Leaderboard' }} />
          <Stack.Screen name="taste-profile/[userId]" options={{ title: 'Taste Profile' }} />
          <Stack.Screen name="settings" options={{ title: 'Settings' }} />
          <Stack.Screen name="legal/privacy" options={{ title: 'Privacy Policy' }} />
          <Stack.Screen name="legal/terms" options={{ title: 'Terms of Service' }} />
        </Stack>
        <ToastContainer />
      </View>
    </QueryClientProvider>
    </ErrorBoundary>
  );
}
