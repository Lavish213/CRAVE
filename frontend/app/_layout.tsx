import { useEffect } from 'react';
import { AppState, Platform, View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Stack, useRouter, type ErrorBoundaryProps } from 'expo-router';
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
import { Colors, Spacing, Typography } from '../src/constants/colors';
import { ToastContainer } from '../src/components/Toast';
import { AuthGateHost } from '../src/components/AuthGateHost';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

const eb = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.background,
    padding: Spacing.xl,
  },
  title: {
    ...Typography.title,
    color: Colors.text,
    marginBottom: Spacing.sm,
  },
  body: {
    ...Typography.body,
    color: Colors.textSecondary,
    textAlign: 'center',
    marginBottom: Spacing.lg,
  },
  btn: {
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.lg,
    minHeight: 44,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnText: {
    ...Typography.body,
    color: Colors.text,
    fontWeight: '700',
  },
});

/**
 * Expo Router route error boundary for the root layout.
 *
 * The previous class boundary only flipped its own `hasError` boolean to
 * false. A deterministic route/layout crash therefore rendered the exact
 * same broken tree again without asking the router to retry the failed route.
 * SDK55 exposes ErrorBoundaryProps.retry specifically for this recovery path;
 * use that framework-owned reset instead of maintaining a second error state.
 */
export function ErrorBoundary({ retry }: ErrorBoundaryProps) {
  return (
    <View style={eb.container}>
      <Text style={eb.title}>Something went wrong</Text>
      <Text style={eb.body}>CRAVE hit an unexpected error.</Text>
      <TouchableOpacity
        style={eb.btn}
        onPress={retry}
        accessibilityRole="button"
        accessibilityLabel="Retry loading CRAVE"
      >
        <Text style={eb.btnText}>Try again</Text>
      </TouchableOpacity>
    </View>
  );
}

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

  useEffect(() => {
    if (Platform.OS === 'web') return;

    function routeFromNotificationData(data: Record<string, unknown> | undefined) {
      const placeId = data?.placeId;
      if (typeof placeId === 'string' && placeId) {
        router.push(`/place/${placeId}`);
      }
    }

    Notifications.getLastNotificationResponseAsync().then((response) => {
      if (response) {
        routeFromNotificationData(
          response.notification.request.content.data as Record<string, unknown>,
        );
      }
    }).catch(() => {});

    const subscription = Notifications.addNotificationResponseReceivedListener((response) => {
      routeFromNotificationData(
        response.notification.request.content.data as Record<string, unknown>,
      );
    });
    return () => subscription.remove();
  }, [router]);

  useEffect(() => {
    initAuth();
    initCities();
  }, [initAuth, initCities]);

  useEffect(() => {
    if (user?.id) {
      void loadSaves(user.id);
    }
  }, [user?.id, loadSaves]);

  useEffect(() => {
    setActiveUserForVideoSync(user?.id ?? null);
    if (user?.id) {
      runVideoSyncPass(user.id).catch(() => {});
    }
  }, [user?.id, runVideoSyncPass]);

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
          <Stack.Screen name="record-video/[placeId]" options={{ headerShown: false }} />
          <Stack.Screen name="place/[id]" options={{ title: '', animation: 'fade_from_bottom' }} />
          <Stack.Screen name="rank/[placeId]" options={{ title: 'Rank this place', animation: 'fade_from_bottom' }} />
          <Stack.Screen name="user/[id]" options={{ title: '' }} />
          <Stack.Screen name="profile-setup" options={{ title: 'Set up profile' }} />
          <Stack.Screen name="add-spot" options={{ title: 'Add a Spot' }} />
          <Stack.Screen name="friends-feed" options={{ title: 'Friends' }} />
          <Stack.Screen name="leaderboard" options={{ title: 'Leaderboard' }} />
          <Stack.Screen name="taste-profile/[userId]" options={{ title: 'Taste Profile' }} />
          <Stack.Screen name="settings" options={{ title: 'Settings' }} />
          <Stack.Screen name="legal/privacy" options={{ title: 'Privacy Policy' }} />
          <Stack.Screen name="legal/terms" options={{ title: 'Terms of Service' }} />
        </Stack>
        <AuthGateHost />
        <ToastContainer />
      </View>
    </QueryClientProvider>
  );
}
