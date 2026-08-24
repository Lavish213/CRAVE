import { useEffect, Component, ReactNode } from 'react';
import { AppState, View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useCityStore } from '../src/stores/cityStore';
import { useAuthStore } from '../src/stores/authStore';
import { useCravesStore } from '../src/stores/cravesStore';
import { useVideoQueueStore, setActiveUserForVideoSync } from '../src/stores/videoQueueStore';
import { pingStreak } from '../src/api/streak';
import { Colors, Spacing } from '../src/constants/colors';
import { ToastContainer } from '../src/components/Toast';

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
  body: { fontSize: 14, color: Colors.textMuted, textAlign: 'center', marginBottom: Spacing.lg },
  btn: { backgroundColor: Colors.primary, paddingHorizontal: Spacing.lg, paddingVertical: Spacing.sm, borderRadius: 8 },
  btnText: { color: Colors.text, fontWeight: '700', fontSize: 14 },
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,     // 2 min default
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function RootLayout() {
  const initCities = useCityStore((s) => s.initCities);
  const initAuth = useAuthStore((s) => s.init);
  const user = useAuthStore((s) => s.user);
  const loadSaves = useCravesStore((s) => s.loadSaves);
  const runVideoSyncPass = useVideoQueueStore((s) => s.runSyncPass);

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
          <Stack.Screen name="place/[id]" options={{ title: '', animation: 'fade_from_bottom' }} />
          <Stack.Screen name="rank/[placeId]" options={{ title: 'Rank this place', animation: 'fade_from_bottom' }} />
          <Stack.Screen name="user/[id]" options={{ title: '' }} />
          <Stack.Screen name="profile-setup" options={{ title: 'Set up profile' }} />
          <Stack.Screen name="friends-feed" options={{ title: 'Friends' }} />
          <Stack.Screen name="leaderboard" options={{ title: 'Leaderboard' }} />
          <Stack.Screen name="taste-profile/[userId]" options={{ title: 'Taste Profile' }} />
          <Stack.Screen name="settings" options={{ title: 'Settings' }} />
        </Stack>
        <ToastContainer />
      </View>
    </QueryClientProvider>
    </ErrorBoundary>
  );
}
