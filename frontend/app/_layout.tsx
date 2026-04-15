import { useEffect } from 'react';
import { View } from 'react-native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { fetchCities } from '../src/api/cities';
import { useCityStore } from '../src/stores/cityStore';
import { Colors } from '../src/constants/colors';
import { ToastContainer } from '../src/components/Toast';

export default function RootLayout() {
  const setCities = useCityStore((s) => s.setCities);
  const selectCity = useCityStore((s) => s.selectCity);
  const selectedCity = useCityStore((s) => s.selectedCity);

  useEffect(() => {
    fetchCities()
      .then((cities) => {
        setCities(cities);
        // Auto-select first city if none selected
        if (!selectedCity && cities.length > 0) {
          selectCity(cities[0]);
        }
      })
      .catch(() => {});
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
