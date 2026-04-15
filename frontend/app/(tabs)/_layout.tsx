import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing } from '../../src/constants/colors';

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
  return (
    <Tabs
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
        name="map"
        options={{
          title: 'Map',
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} iconFocused="map" iconUnfocused="map-outline" />
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
        name="hitlist"
        options={{
          title: 'Hit List',
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} iconFocused="bookmark" iconUnfocused="bookmark-outline" />
          ),
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: 'More',
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} iconFocused="person-circle" iconUnfocused="person-circle-outline" />
          ),
        }}
      />
    </Tabs>
  );
}
