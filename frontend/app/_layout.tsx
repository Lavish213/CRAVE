import { useEffect } from 'react';
import { View } from 'react-native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCityStore } from '../src/stores/cityStore';
import { useAuthStore } from '../src/stores/authStore';
import { Colors } from '../src/constants/colors';
import { ToastContainer } from '../src/components/Toast';

export default function RootLayout() {
  const initCities = useCityStore((s) => s.initCities);
  const initAuth = useAuthStore((s) => s.init);

  useEffect(() => {
    initAuth();
    initCities();
  }, []);

  return (
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
  );
}
