import { useEffect } from 'react';
import { View } from 'react-native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useCityStore } from '../src/stores/cityStore';
import { useAuthStore } from '../src/stores/authStore';
import { useHitlistStore } from '../src/stores/hitlistStore';
import { Colors } from '../src/constants/colors';
import { ToastContainer } from '../src/components/Toast';

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
  const loadSaves = useHitlistStore((s) => s.loadSaves);

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
          <Stack.Screen name="place/[id]" options={{ title: '' }} />
        </Stack>
        <ToastContainer />
      </View>
    </QueryClientProvider>
  );
}
