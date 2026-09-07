import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Tabs, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius, Spacing } from '../../src/constants/colors';

type IoniconsName = React.ComponentProps<typeof Ionicons>['name'];

function TabIcon({ focused, iconFocused, iconUnfocused }: {
  focused: boolean;
  iconFocused: IoniconsName;
  iconUnfocused: IoniconsName;
}) {
  return (
    <Ionicons
      name={focused ? iconFocused : iconUnfocused}
      size={24}
      color={focused ? Colors.primary : Colors.textSecondary}
    />
  );
}

export default function TabLayout() {
  const router = useRouter();

  return (
    <View style={styles.container}>
      <Tabs
        initialRouteName="index"
        screenOptions={{
          tabBarStyle: {
            backgroundColor: Colors.surface,
            borderTopColor: Colors.border,
            height: 80,
            paddingBottom: Spacing.lg,
          },
          tabBarActiveTintColor: Colors.primary,
          tabBarInactiveTintColor: Colors.textSecondary,
          headerStyle: { backgroundColor: Colors.background },
          headerTintColor: Colors.text,
          headerTitleStyle: { fontWeight: '700' },
          headerRight: () => (
            <Pressable
              onPress={() => router.push('/activity')}
              accessibilityRole="button"
              accessibilityLabel="Open Activity"
              hitSlop={10}
              style={styles.headerAction}
            >
              <Ionicons name="notifications-outline" size={22} color={Colors.text} />
            </Pressable>
          ),
        }}
      >
        <Tabs.Screen
          name="index"
          options={{
            title: 'Feed',
            tabBarIcon: ({ focused }) => (
              <TabIcon focused={focused} iconFocused="home" iconUnfocused="home-outline" />
            ),
          }}
        />
        <Tabs.Screen
          name="search"
          options={{
            title: 'Search',
            tabBarIcon: ({ focused }) => (
              <TabIcon focused={focused} iconFocused="search" iconUnfocused="search-outline" />
            ),
          }}
        />
        <Tabs.Screen
          name="craves"
          options={{
            title: 'Craves',
            tabBarIcon: ({ focused }) => (
              <TabIcon focused={focused} iconFocused="bookmark" iconUnfocused="bookmark-outline" />
            ),
          }}
        />
        <Tabs.Screen
          name="rank"
          options={{
            title: 'Rank',
            tabBarIcon: ({ focused }) => (
              <TabIcon focused={focused} iconFocused="podium" iconUnfocused="podium-outline" />
            ),
          }}
        />
        <Tabs.Screen
          name="profile"
          options={{
            title: 'Profile',
            tabBarIcon: ({ focused }) => (
              <TabIcon focused={focused} iconFocused="person-circle" iconUnfocused="person-circle-outline" />
            ),
          }}
        />
        <Tabs.Screen
          name="map"
          options={{
            href: null,
            title: 'Map',
          }}
        />
      </Tabs>

      <Pressable
        onPress={() => router.push('/food-evidence')}
        accessibilityRole="button"
        accessibilityLabel="Record food evidence"
        style={({ pressed }) => [styles.recordAction, pressed && styles.recordActionPressed]}
      >
        <Ionicons name="add" size={28} color={Colors.background} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  headerAction: {
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.sm,
  },
  recordAction: {
    position: 'absolute',
    right: Spacing.lg,
    bottom: 92,
    width: 52,
    height: 52,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary,
    shadowColor: '#000000',
    shadowOpacity: 0.28,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 5,
  },
  recordActionPressed: { opacity: 0.85 },
});
