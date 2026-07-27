import { useEffect, Component, ReactNode } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useCityStore } from '../src/stores/cityStore';
import { useAuthStore } from '../src/stores/authStore';
import { useHitlistStore } from '../src/stores/hitlistStore';
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
          <Stack.Screen name="place/[id]" options={{ title: '' }} />
        </Stack>
        <ToastContainer />
      </View>
    </QueryClientProvider>
    </ErrorBoundary>
  );
}
