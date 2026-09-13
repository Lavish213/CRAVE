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
import { usePostingDraftStore, setActiveUserForDraftResolution } from '../src/stores/postingDraftStore';
import { usePushNotifications } from '../src/hooks/usePushNotifications';
import { pingStreak } from '../src/api/streak';
import { isSupabaseConfigured } from '../src/lib/supabase';
import { Colors, Spacing, Typography } from '../src/constants/colors';
import { ToastContainer } from '../src/components/Toast';
import { AuthGateHost } from '../src/components/AuthGateHost';
import { useToast } from '../src/hooks/useToast';

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

export function notificationRouteFromData(
  data: Record<string, unknown> | undefined,
): `/place/${string}` | null {
  const placeId = data?.placeId;
  return typeof placeId === 'string' && placeId.trim()
    ? `/place/${encodeURIComponent(placeId)}`
    : null;
}

function ConfigErrorScreen() {
  return (
    <View style={eb.container}>
      <Text style={eb.title}>Configuration error</Text>
      <Text style={eb.body}>
        {__DEV__
          ? "CRAVE can't start because its Supabase configuration is missing. Check frontend/.env and restart the development build."
          : "CRAVE can't start because this build is missing required configuration. Please install the latest build or contact support."}
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
  const resolvePendingCandidates = usePostingDraftStore((s) => s.resolvePendingCandidates);
  const toast = useToast((s) => s.show);

  usePushNotifications(user?.id);

  useEffect(() => {
    if (Platform.OS === 'web') return;

    function routeFromNotificationData(data: Record<string, unknown> | undefined): boolean {
      const destination = notificationRouteFromData(data);
      if (!destination) return false;
      router.push(destination);
      return true;
    }

    Notifications.getLastNotificationResponseAsync().then((response) => {
      if (response) {
        if (!routeFromNotificationData(
          response.notification.request.content.data as Record<string, unknown>,
        )) toast("That notification's destination is no longer available.");
      }
    }).catch((err) => {
      if (__DEV__) console.warn('[notifications] Failed to recover the last response:', err);
      toast("Couldn't open the notification. Try again from Activity.");
    });

    const subscription = Notifications.addNotificationResponseReceivedListener((response) => {
      if (!routeFromNotificationData(
        response.notification.request.content.data as Record<string, unknown>,
      )) toast("That notification's destination is no longer available.");
    });
    return () => subscription.remove();
  }, [router, toast]);

  useEffect(() => {
    const cleanupAuth = initAuth();
    initCities();
    return cleanupAuth;
  }, [initAuth, initCities]);

  useEffect(() => {
    if (user?.id) {
      void loadSaves(user.id);
    }
  }, [user?.id, loadSaves]);

  useEffect(() => {
    setActiveUserForVideoSync(user?.id ?? null);
    if (user?.id) {
      runVideoSyncPass(user.id).catch((err) => {
        if (__DEV__) console.warn('[video-sync] Background sync pass failed; queue retained:', err);
      });
    }
  }, [user?.id, runVideoSyncPass]);

  // Posting drafts left with restaurantRef=candidate (a place CRAVE
  // didn't have yet when captured) get checked against the promotion
  // pipeline here too -- same "on sign-in, then on every foreground"
  // trigger as the video queue above.
  useEffect(() => {
    setActiveUserForDraftResolution(user?.id ?? null);
    if (user?.id) {
      resolvePendingCandidates(user.id).catch((err) => {
        if (__DEV__) console.warn('[drafts] Candidate resolution failed; drafts retained:', err);
      });
    }
  }, [user?.id, resolvePendingCandidates]);

  useEffect(() => {
    if (!user?.id) return;
    pingStreak().catch((err) => {
      if (__DEV__) console.warn('[streak] Background ping failed:', err);
    });
    const subscription = AppState.addEventListener('change', (nextState) => {
      if (nextState === 'active') {
        pingStreak().catch((err) => {
          if (__DEV__) console.warn('[streak] Foreground ping failed:', err);
        });
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
          <Stack.Screen name="activity" options={{ title: 'Activity' }} />
          <Stack.Screen
            name="food-evidence"
            options={{ title: 'Record a meal', presentation: 'modal' }}
          />
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
