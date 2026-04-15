# CRAVE Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the CRAVE frontend to production quality — unified tier system, extracted components, error/empty states, polished screens, fixed map, and the Crave Loop.

**Architecture:** Extract inlined components to `src/components/`, fix the three-way tier color split via a single source of truth in `scoring.ts`, add error/toast/empty infrastructure, then polish each screen in order of user impact.

**Tech Stack:** Expo 54 · React Native 0.81.5 · expo-router · Zustand + AsyncStorage · TypeScript strict · expo-image · expo-haptics · react-native-maps

---

## File Map

### Create
- `src/components/TierBadge.tsx` — tier pill (label + color), single source
- `src/components/TrustLine.tsx` — one-line signal context text
- `src/components/ErrorState.tsx` — retry button + message
- `src/components/EmptyState.tsx` — icon + title + body + CTA button
- `src/components/Toast.tsx` — ephemeral bottom notification
- `src/components/PlaceCard.tsx` — feed card (extracted from index.tsx)
- `src/components/PlaceCardCompact.tsx` — search/hitlist row card
- `src/components/SectionHeader.tsx` — section label + subtext + count
- `src/components/CitySelectorStrip.tsx` — horizontal city pills
- `src/components/TrendingStrip.tsx` — horizontal trending chips
- `src/components/ImageGallery.tsx` — full-width image gallery + dots
- `src/components/TrustBadgeRow.tsx` — horizontal scrolling trust badges
- `src/components/MapMarker.tsx` — custom colored map pin
- `src/components/MapBottomSheet.tsx` — pin-tap preview sheet
- `src/hooks/useToast.ts` — toast trigger hook
- `src/api/search.ts` — searchPlaces() function
- `src/api/menu.ts` — getPlaceMenu() function
- `src/api/crave.ts` — getCraveItems() function
- `assets/placeholder-food.png` — copy from existing assets or use icon.png

### Modify
- `app.json` — dark userInterfaceStyle, dark splash bg
- `src/constants/colors.ts` — add 4 canonical tier colors, remove unused tokens
- `src/utils/scoring.ts` — add sectionSubtext, fix label copy ("Hidden Gem"/"Worth Knowing"/"Explore")
- `src/stores/cityStore.ts` — add AsyncStorage persistence
- `app/_layout.tsx` — add Toast provider, fix city auto-select race
- `app/(tabs)/index.tsx` — use extracted components, fix getTier, error state, cancel ref
- `app/(tabs)/search.tsx` — use api/search.ts, city label, debounce, clear, PlaceCardCompact
- `app/(tabs)/map.tsx` — custom markers, bottom sheet, city selector, import from scoring.ts
- `app/(tabs)/hitlist.tsx` — fix empty copy, use PlaceCardCompact, Craves section
- `app/place/[id].tsx` — use ImageGallery/TrustBadgeRow, directions button, local placeholder

### Delete
- `App.tsx` — dead Expo stub

### Remove from package.json
- `nativewind` — installed but never used
- `tailwindcss` — same

---

## Phase 1 — Foundation + Trust Clarity

---

### Task 1: Fix app.json + delete dead files

**Files:**
- Modify: `app.json`
- Delete: `App.tsx`

- [ ] **Step 1: Fix app.json dark theme**

Open `app.json`. Change `"userInterfaceStyle": "light"` to `"dark"`. Change the `"splash"` `"backgroundColor"` from `"#ffffff"` to `"#0A0A0A"`. Add `"backgroundColor": "#0A0A0A"` under `"android"` config if not present.

The relevant section should look like:
```json
{
  "expo": {
    "userInterfaceStyle": "dark",
    "splash": {
      "image": "./assets/splash-icon.png",
      "resizeMode": "contain",
      "backgroundColor": "#0A0A0A"
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#0A0A0A"
      }
    }
  }
}
```

- [ ] **Step 2: Delete App.tsx**

```bash
cd /Users/angelowashington/CRAVE/frontend && rm App.tsx
```

- [ ] **Step 3: Verify TypeScript still compiles**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```
Expected: no errors (App.tsx was unused, removing it changes nothing).

- [ ] **Step 4: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "fix: dark theme app.json, remove dead App.tsx stub"
```

---

### Task 2: Unify tier + color system

**Files:**
- Modify: `src/constants/colors.ts`
- Modify: `src/utils/scoring.ts`

- [ ] **Step 1: Rewrite colors.ts**

Replace the entire file:

```typescript
// src/constants/colors.ts
export const Colors = {
  // UI chrome
  primary:         '#FF3B30',
  background:      '#0A0A0A',
  surface:         '#1A1A1A',
  surfaceElevated: '#252525',
  border:          '#2A2A2A',
  text:            '#FFFFFF',
  textSecondary:   '#888888',
  textMuted:       '#555555',
  // Semantic
  success:         '#30D158',
  warning:         '#FF9F0A',
  error:           '#FF453A',
  // Tier — canonical, imported by scoring.ts and map.tsx
  tierCravePick:   '#FF4D00',
  tierGem:         '#FFB800',
  tierSolid:       '#4CAF50',
  tierNew:         '#666666',
} as const;

export type ColorKey = keyof typeof Colors;
```

- [ ] **Step 2: Rewrite scoring.ts**

Replace the entire file:

```typescript
// src/utils/scoring.ts
import { PlaceOut } from '../api/places';
import { Colors } from '../constants/colors';

export type TierKey = 'crave_pick' | 'gem' | 'solid' | 'new';

export interface Tier {
  key: TierKey;
  label: string;
  color: string;
  sectionLabel: string;
  sectionSubtext: string;
}

export const TIERS: Record<TierKey, Tier> = {
  crave_pick: {
    key: 'crave_pick',
    label: 'CRAVE Pick',
    color: Colors.tierCravePick,
    sectionLabel: 'CRAVE Picks',
    sectionSubtext: 'The strongest signals in the city',
  },
  gem: {
    key: 'gem',
    label: 'Hidden Gem',
    color: Colors.tierGem,
    sectionLabel: 'Hidden Gems',
    sectionSubtext: 'Off the beaten path, locally loved',
  },
  solid: {
    key: 'solid',
    label: 'Worth Knowing',
    color: Colors.tierSolid,
    sectionLabel: 'Worth Knowing',
    sectionSubtext: 'Solid choices with real upside',
  },
  new: {
    key: 'new',
    label: 'Explore',
    color: Colors.tierNew,
    sectionLabel: 'Explore',
    sectionSubtext: 'New to CRAVE or still emerging',
  },
};

export function getTier(score: number): Tier {
  if (score >= 0.42) return TIERS.crave_pick;
  if (score >= 0.32) return TIERS.gem;
  if (score >= 0.22) return TIERS.solid;
  return TIERS.new;
}

export function getSignalContext(place: PlaceOut): string {
  const tier = getTier(place.rank_score);
  switch (tier.key) {
    case 'crave_pick':
      if (place.has_menu && place.grubhub_url) return 'Full menu · Online ordering · Top ranked';
      if (place.has_menu) return 'Full menu · Culturally validated';
      return 'Locally loved · Off the beaten path';
    case 'gem':
      if (!place.has_menu && !place.grubhub_url) return 'Off the grid · Locals know this';
      if (!place.grubhub_url) return 'Community favorite · No delivery';
      return 'Local pick · Worth the visit';
    case 'solid':
      if (place.has_menu) return 'Menu available · Reliable choice';
      if (place.website) return 'Established · Worth exploring';
      return 'Solid choice';
    case 'new':
    default:
      return 'New to CRAVE · Still gaining signal';
  }
}

export interface TrustBadge {
  label: string;
  color: string;
  bg: string;
}

export function getTrustBadges(place: PlaceOut): TrustBadge[] {
  const badges: TrustBadge[] = [];
  const tier = getTier(place.rank_score);
  if (tier.key === 'crave_pick')
    badges.push({ label: 'CRAVE Pick', color: Colors.tierCravePick, bg: '#FF4D0022' });
  if (tier.key === 'gem')
    badges.push({ label: 'Hidden Gem', color: Colors.tierGem, bg: '#FFB80022' });
  if (place.has_menu)
    badges.push({ label: 'Full menu', color: Colors.tierSolid, bg: '#4CAF5022' });
  if (place.grubhub_url)
    badges.push({ label: 'Order online', color: Colors.textSecondary, bg: '#88888822' });
  if (place.website && !place.grubhub_url)
    badges.push({ label: 'Dine in only', color: Colors.textSecondary, bg: '#88888822' });
  if (!place.has_menu && !place.grubhub_url && !place.website)
    badges.push({ label: 'Off the grid', color: Colors.tierGem, bg: '#FFB80022' });
  return badges;
}
```

- [ ] **Step 3: Verify compilation**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: unify tier/color system — single source of truth in colors.ts + scoring.ts"
```

---

### Task 3: Create TierBadge + TrustLine components

**Files:**
- Create: `src/components/TierBadge.tsx`
- Create: `src/components/TrustLine.tsx`

- [ ] **Step 1: Create TierBadge.tsx**

```typescript
// src/components/TierBadge.tsx
import React from 'react';
import { StyleSheet, Text, View, ViewStyle } from 'react-native';
import { Tier } from '../utils/scoring';

interface Props {
  tier: Tier;
  style?: ViewStyle;
}

export function TierBadge({ tier, style }: Props) {
  return (
    <View style={[styles.badge, { backgroundColor: tier.color + 'DD' }, style]}>
      <Text style={styles.label}>{tier.label.toUpperCase()}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    alignSelf: 'flex-start',
  },
  label: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 0.8,
  },
});
```

- [ ] **Step 2: Create TrustLine.tsx**

```typescript
// src/components/TrustLine.tsx
import React from 'react';
import { StyleSheet, Text, TextStyle } from 'react-native';

interface Props {
  text: string;
  color: string;
  style?: TextStyle;
  numberOfLines?: number;
}

export function TrustLine({ text, color, style, numberOfLines = 1 }: Props) {
  return (
    <Text
      style={[styles.text, { color }, style]}
      numberOfLines={numberOfLines}
    >
      {text}
    </Text>
  );
}

const styles = StyleSheet.create({
  text: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
});
```

- [ ] **Step 3: Verify compilation**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: TierBadge and TrustLine components"
```

---

### Task 4: Create ErrorState + EmptyState components

**Files:**
- Create: `src/components/ErrorState.tsx`
- Create: `src/components/EmptyState.tsx`

- [ ] **Step 1: Create ErrorState.tsx**

```typescript
// src/components/ErrorState.tsx
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../constants/colors';

interface Props {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({ message = 'Something went wrong', onRetry }: Props) {
  return (
    <View style={styles.container}>
      <Ionicons name="cloud-offline-outline" size={40} color={Colors.textMuted} />
      <Text style={styles.message}>{message}</Text>
      {onRetry && (
        <TouchableOpacity style={styles.retryBtn} onPress={onRetry} activeOpacity={0.75}>
          <Text style={styles.retryText}>Try again</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    paddingHorizontal: 32,
    paddingTop: 60,
  },
  message: { color: Colors.textSecondary, fontSize: 15, textAlign: 'center' },
  retryBtn: {
    marginTop: 4,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.border,
    minHeight: 44,
    justifyContent: 'center',
  },
  retryText: { color: Colors.text, fontSize: 14, fontWeight: '600' },
});
```

- [ ] **Step 2: Create EmptyState.tsx**

```typescript
// src/components/EmptyState.tsx
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../constants/colors';

interface Props {
  icon?: keyof typeof Ionicons.glyphMap;
  title: string;
  body?: string;
  ctaLabel?: string;
  onCta?: () => void;
}

export function EmptyState({ icon = 'search-outline', title, body, ctaLabel, onCta }: Props) {
  return (
    <View style={styles.container}>
      <Ionicons name={icon} size={44} color={Colors.textMuted} />
      <Text style={styles.title}>{title}</Text>
      {body ? <Text style={styles.body}>{body}</Text> : null}
      {ctaLabel && onCta ? (
        <TouchableOpacity style={styles.cta} onPress={onCta} activeOpacity={0.75}>
          <Text style={styles.ctaText}>{ctaLabel}</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    paddingHorizontal: 32,
    paddingTop: 60,
  },
  title: { color: Colors.text, fontSize: 18, fontWeight: '700', textAlign: 'center' },
  body: { color: Colors.textSecondary, fontSize: 14, textAlign: 'center', lineHeight: 20 },
  cta: {
    marginTop: 6,
    paddingHorizontal: 22,
    paddingVertical: 11,
    borderRadius: 22,
    backgroundColor: Colors.primary,
    minHeight: 44,
    justifyContent: 'center',
  },
  ctaText: { color: '#FFFFFF', fontSize: 14, fontWeight: '700' },
});
```

- [ ] **Step 3: Verify**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: ErrorState and EmptyState components"
```

---

### Task 5: Add Toast system

**Files:**
- Create: `src/components/Toast.tsx`
- Create: `src/hooks/useToast.ts`
- Modify: `app/_layout.tsx`

- [ ] **Step 1: Create useToast.ts**

```typescript
// src/hooks/useToast.ts
import { create } from 'zustand';

interface ToastState {
  message: string | null;
  show: (msg: string, durationMs?: number) => void;
  hide: () => void;
}

let _timer: ReturnType<typeof setTimeout> | null = null;

export const useToast = create<ToastState>((set) => ({
  message: null,
  show: (msg, durationMs = 2800) => {
    if (_timer) clearTimeout(_timer);
    set({ message: msg });
    _timer = setTimeout(() => set({ message: null }), durationMs);
  },
  hide: () => {
    if (_timer) clearTimeout(_timer);
    set({ message: null });
  },
}));
```

- [ ] **Step 2: Create Toast.tsx**

```typescript
// src/components/Toast.tsx
import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text } from 'react-native';
import * as Haptics from 'expo-haptics';
import { useToast } from '../hooks/useToast';
import { Colors } from '../constants/colors';

export function ToastContainer() {
  const message = useToast((s) => s.message);
  const opacity = useRef(new Animated.Value(0)).current;
  const prevMessage = useRef<string | null>(null);

  useEffect(() => {
    if (message && message !== prevMessage.current) {
      prevMessage.current = message;
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 180, useNativeDriver: true }),
      ]).start();
    }
    if (!message) {
      Animated.timing(opacity, { toValue: 0, duration: 220, useNativeDriver: true }).start(() => {
        prevMessage.current = null;
      });
    }
  }, [message]);

  if (!message && opacity.__getValue() === 0) return null;

  return (
    <Animated.View style={[styles.container, { opacity }]} pointerEvents="none">
      <Text style={styles.text}>{message}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 96,
    left: 24,
    right: 24,
    backgroundColor: '#2A2A2AEE',
    borderRadius: 12,
    paddingHorizontal: 18,
    paddingVertical: 13,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.4,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 10,
    zIndex: 9999,
  },
  text: { color: Colors.text, fontSize: 14, fontWeight: '600', textAlign: 'center' },
});
```

- [ ] **Step 3: Add ToastContainer to _layout.tsx**

Replace `app/_layout.tsx` with:

```typescript
// app/_layout.tsx
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
        if (!selectedCity && cities.length > 0) {
          selectCity(cities[0]);
        }
      })
      .catch(() => {});
  }, []);

  return (
    <View style={{ flex: 1 }}>
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
```

- [ ] **Step 4: Verify**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: Toast system — useToast store + ToastContainer in layout"
```

---

### Task 6: Extract PlaceCard + SectionHeader components

**Files:**
- Create: `src/components/PlaceCard.tsx`
- Create: `src/components/SectionHeader.tsx`

- [ ] **Step 1: Create SectionHeader.tsx**

```typescript
// src/components/SectionHeader.tsx
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Colors } from '../constants/colors';

interface Props {
  label: string;
  subtext: string;
  count: number;
}

export function SectionHeader({ label, subtext, count }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.top}>
        <Text style={styles.label}>{label}</Text>
        <Text style={styles.count}>{count}</Text>
      </View>
      <Text style={styles.subtext}>{subtext}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingTop: 24, paddingBottom: 10, paddingHorizontal: 4 },
  top: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 2 },
  label: { fontSize: 17, fontWeight: '800', color: Colors.text, letterSpacing: 0.3, flex: 1 },
  count: { fontSize: 13, color: Colors.textMuted, fontWeight: '500' },
  subtext: { fontSize: 12, color: Colors.textSecondary, fontWeight: '400' },
});
```

- [ ] **Step 2: Create PlaceCard.tsx**

```typescript
// src/components/PlaceCard.tsx
import React from 'react';
import {
  StyleSheet, Text, TouchableOpacity, View, ViewStyle,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { PlaceOut } from '../api/places';
import { getTier, getSignalContext } from '../utils/scoring';
import { TierBadge } from './TierBadge';
import { TrustLine } from './TrustLine';
import { Colors } from '../constants/colors';

interface Props {
  place: PlaceOut;
  onPress: () => void;
  onSave: () => void;
  saved: boolean;
  style?: ViewStyle;
}

export function PlaceCard({ place, onPress, onSave, saved, style }: Props) {
  const tier = getTier(place.rank_score);
  const context = getSignalContext(place);

  return (
    <TouchableOpacity
      style={[styles.card, style]}
      onPress={() => {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        onPress();
      }}
      activeOpacity={0.85}
      accessibilityRole="button"
      accessibilityLabel={`${place.name}, ${place.category ?? 'Restaurant'}, ${tier.label}`}
    >
      <View style={styles.imageContainer}>
        <Image
          source={place.primary_image_url ?? undefined}
          style={styles.image}
          contentFit="cover"
          placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
          transition={200}
        />
        {/* gradient overlay */}
        <View style={styles.imageGradient} />

        {/* Tier badge — top left */}
        <TierBadge tier={tier} style={styles.tierBadge} />

        {/* Save — top right */}
        <TouchableOpacity
          style={styles.saveBtn}
          onPress={onSave}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          accessibilityLabel={saved ? `Remove ${place.name} from hitlist` : `Save ${place.name} to hitlist`}
          accessibilityRole="button"
        >
          <Ionicons name={saved ? 'bookmark' : 'bookmark-outline'} size={20} color={Colors.text} />
        </TouchableOpacity>
      </View>

      <View style={styles.body}>
        <Text style={styles.name} numberOfLines={1}>{place.name}</Text>
        <Text style={styles.meta} numberOfLines={1}>
          {place.category ?? 'Restaurant'}
          {place.price_tier ? '  ·  ' + '$'.repeat(place.price_tier) : ''}
        </Text>
        <TrustLine text={context} color={tier.color} />
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  imageContainer: { position: 'relative' },
  image: { width: '100%', height: 190 },
  imageGradient: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 60,
    // simple scrim — LinearGradient not installed, use semi-opaque black
    backgroundColor: 'rgba(0,0,0,0.25)',
  },
  tierBadge: { position: 'absolute', top: 10, left: 10 },
  saveBtn: {
    position: 'absolute',
    top: 6,
    right: 10,
    padding: 6,
    backgroundColor: 'rgba(0,0,0,0.45)',
    borderRadius: 20,
  },
  body: { padding: 12, paddingTop: 10, gap: 3 },
  name: { fontSize: 17, fontWeight: '700', color: Colors.text },
  meta: { fontSize: 13, color: Colors.textSecondary },
});
```

- [ ] **Step 3: Verify**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: PlaceCard and SectionHeader components extracted"
```

---

### Task 7: Extract CitySelectorStrip, TrendingStrip, PlaceCardCompact

**Files:**
- Create: `src/components/CitySelectorStrip.tsx`
- Create: `src/components/TrendingStrip.tsx`
- Create: `src/components/PlaceCardCompact.tsx`

- [ ] **Step 1: Create CitySelectorStrip.tsx**

```typescript
// src/components/CitySelectorStrip.tsx
import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity } from 'react-native';
import * as Haptics from 'expo-haptics';
import { useCityStore } from '../stores/cityStore';
import { Colors } from '../constants/colors';

export function CitySelectorStrip() {
  const cities = useCityStore((s) => s.cities);
  const selectedCity = useCityStore((s) => s.selectedCity);
  const selectCity = useCityStore((s) => s.selectCity);

  if (cities.length === 0) return null;

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={styles.strip}
      contentContainerStyle={styles.content}
    >
      {cities.map((city) => {
        const active = selectedCity?.id === city.id;
        return (
          <TouchableOpacity
            key={city.id}
            style={[styles.pill, active && styles.pillActive]}
            onPress={() => { Haptics.selectionAsync(); selectCity(city); }}
            activeOpacity={0.75}
            hitSlop={{ top: 8, bottom: 8, left: 4, right: 4 }}
            accessibilityLabel={`Select ${city.name}`}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
          >
            <Text style={[styles.pillText, active && styles.pillTextActive]}>
              {city.name}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  strip: { flexGrow: 0 },
  content: { paddingHorizontal: 12, paddingVertical: 8, gap: 8 },
  pill: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    minHeight: 36,
    justifyContent: 'center',
  },
  pillActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  pillText: { color: Colors.textSecondary, fontSize: 13, fontWeight: '500' },
  pillTextActive: { color: Colors.text, fontWeight: '700' },
});
```

- [ ] **Step 2: Create TrendingStrip.tsx**

```typescript
// src/components/TrendingStrip.tsx
import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import * as Haptics from 'expo-haptics';
import { PlaceOut } from '../api/places';
import { getTier } from '../utils/scoring';
import { Colors } from '../constants/colors';

interface Props {
  places: PlaceOut[];
  onPress: (id: string) => void;
}

export function TrendingStrip({ places, onPress }: Props) {
  if (places.length === 0) return null;
  return (
    <View style={styles.container}>
      <Text style={styles.heading}>TRENDING</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {places.map((p) => {
          const tier = getTier(p.rank_score);
          return (
            <TouchableOpacity
              key={p.id}
              style={styles.chip}
              onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); onPress(p.id); }}
              activeOpacity={0.8}
              accessibilityLabel={`${p.name}, trending`}
              accessibilityRole="button"
            >
              <View style={[styles.dot, { backgroundColor: tier.color }]} />
              <Text style={styles.chipText} numberOfLines={1}>{p.name}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 4 },
  heading: {
    fontSize: 10,
    fontWeight: '800',
    color: Colors.textMuted,
    letterSpacing: 1.5,
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 4,
  },
  scroll: { paddingHorizontal: 12, gap: 8, paddingBottom: 4 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Colors.surface,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: Colors.border,
    minHeight: 36,
  },
  dot: { width: 7, height: 7, borderRadius: 4 },
  chipText: { color: Colors.text, fontSize: 13, fontWeight: '500', maxWidth: 130 },
});
```

- [ ] **Step 3: Create PlaceCardCompact.tsx**

```typescript
// src/components/PlaceCardCompact.tsx
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View, ViewStyle } from 'react-native';
import { Image } from 'expo-image';
import * as Haptics from 'expo-haptics';
import { PlaceOut } from '../api/places';
import { getTier, getSignalContext } from '../utils/scoring';
import { TierBadge } from './TierBadge';
import { TrustLine } from './TrustLine';
import { Colors } from '../constants/colors';

interface Props {
  place: PlaceOut;
  onPress: () => void;
  rightAction?: React.ReactNode;
  style?: ViewStyle;
}

export function PlaceCardCompact({ place, onPress, rightAction, style }: Props) {
  const tier = getTier(place.rank_score);
  const context = getSignalContext(place);

  return (
    <TouchableOpacity
      style={[styles.row, style]}
      onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); onPress(); }}
      activeOpacity={0.85}
      accessibilityRole="button"
      accessibilityLabel={`${place.name}, ${place.category ?? 'Restaurant'}, ${tier.label}`}
    >
      <Image
        source={place.primary_image_url ?? undefined}
        style={styles.thumb}
        contentFit="cover"
        placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
      />
      <View style={styles.meta}>
        <View style={styles.nameRow}>
          <Text style={styles.name} numberOfLines={1}>{place.name}</Text>
          <TierBadge tier={tier} />
        </View>
        <Text style={styles.sub} numberOfLines={1}>
          {place.category ?? 'Restaurant'}
          {place.price_tier ? '  ·  ' + '$'.repeat(place.price_tier) : ''}
        </Text>
        <TrustLine text={context} color={tier.color} />
      </View>
      {rightAction}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: 12,
    backgroundColor: Colors.surface,
    borderRadius: 12,
    overflow: 'hidden',
    alignItems: 'center',
    padding: 10,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  thumb: { width: 64, height: 64, borderRadius: 8 },
  meta: { flex: 1, gap: 3 },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  name: { color: Colors.text, fontSize: 15, fontWeight: '600', flex: 1 },
  sub: { color: Colors.textSecondary, fontSize: 13 },
});
```

- [ ] **Step 4: Verify**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: CitySelectorStrip, TrendingStrip, PlaceCardCompact components"
```

---

### Task 8: Add API modules + cityStore persistence

**Files:**
- Create: `src/api/search.ts`
- Create: `src/api/menu.ts`
- Create: `src/api/crave.ts`
- Modify: `src/stores/cityStore.ts`

- [ ] **Step 1: Create src/api/search.ts**

```typescript
// src/api/search.ts
import { client } from './client';
import { PlaceOut } from './places';

export async function searchPlaces(params: {
  q: string;
  city_id: string;
  limit?: number;
}): Promise<PlaceOut[]> {
  const { data } = await client.get<PlaceOut[]>('/api/v1/search', { params });
  return data;
}
```

- [ ] **Step 2: Create src/api/menu.ts**

```typescript
// src/api/menu.ts
import { client } from './client';

export interface MenuItem {
  id: string;
  name: string;
  description: string | null;
  price: number | null;
  category: string | null;
}

export async function getPlaceMenu(placeId: string): Promise<MenuItem[]> {
  const { data } = await client.get<MenuItem[]>(`/api/v1/places/${placeId}/menu`);
  return data;
}
```

- [ ] **Step 3: Create src/api/crave.ts**

```typescript
// src/api/crave.ts
import { client } from './client';

export interface CraveItem {
  id: string;
  url: string;
  source_type: string;
  parsed_place_name: string | null;
  matched_place_id: string | null;
  match_confidence: number | null;
  status: string;
  created_at: string;
}

export async function getCraveItems(): Promise<CraveItem[]> {
  const { data } = await client.get<CraveItem[]>('/api/v1/craves');
  return data;
}
```

- [ ] **Step 4: Add AsyncStorage persistence to cityStore**

Install dependency if not present:
```bash
cd /Users/angelowashington/CRAVE/frontend && npx expo install @react-native-async-storage/async-storage
```
(Already installed per package.json — skip install, just update store.)

Replace `src/stores/cityStore.ts`:

```typescript
// src/stores/cityStore.ts
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';

export interface City {
  id: string;
  name: string;
  slug: string | null;
  lat: number | null;
  lng: number | null;
}

interface CityStore {
  cities: City[];
  selectedCity: City | null;
  setCities: (cities: City[]) => void;
  selectCity: (city: City) => void;
}

export const useCityStore = create<CityStore>()(
  persist(
    (set) => ({
      cities: [],
      selectedCity: null,
      setCities: (cities) => set({ cities }),
      selectCity: (city) => set({ selectedCity: city }),
    }),
    {
      name: 'crave-city-store',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({ selectedCity: state.selectedCity }),
    },
  ),
);
```

- [ ] **Step 5: Verify**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: api/search, api/menu, api/crave modules + persist cityStore"
```

---

### Task 9: Rewrite Feed screen using extracted components

**Files:**
- Modify: `app/(tabs)/index.tsx`

- [ ] **Step 1: Replace app/(tabs)/index.tsx**

```typescript
// app/(tabs)/index.tsx
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { fetchPlaces, fetchTrending, PlaceOut } from '../../src/api/places';
import { useCityStore } from '../../src/stores/cityStore';
import { useHitlistStore } from '../../src/stores/hitlistStore';
import { useToast } from '../../src/hooks/useToast';
import { Colors } from '../../src/constants/colors';
import { getTier, TIERS } from '../../src/utils/scoring';
import { PlaceCard } from '../../src/components/PlaceCard';
import { SectionHeader } from '../../src/components/SectionHeader';
import { CitySelectorStrip } from '../../src/components/CitySelectorStrip';
import { TrendingStrip } from '../../src/components/TrendingStrip';
import { ErrorState } from '../../src/components/ErrorState';
import { EmptyState } from '../../src/components/EmptyState';
import { SkeletonFeed } from '../../src/components/SkeletonCard';

type FeedRow =
  | { kind: 'header'; tierKey: keyof typeof TIERS }
  | { kind: 'place'; place: PlaceOut };

function buildFeedRows(places: PlaceOut[]): FeedRow[] {
  const sections: { key: keyof typeof TIERS; places: PlaceOut[] }[] = [
    { key: 'crave_pick', places: places.filter((p) => getTier(p.rank_score).key === 'crave_pick') },
    { key: 'gem',        places: places.filter((p) => getTier(p.rank_score).key === 'gem') },
    { key: 'solid',      places: places.filter((p) => getTier(p.rank_score).key === 'solid') },
    { key: 'new',        places: places.filter((p) => getTier(p.rank_score).key === 'new') },
  ];

  const rows: FeedRow[] = [];
  for (const section of sections) {
    if (section.places.length === 0) continue;
    rows.push({ kind: 'header', tierKey: section.key });
    for (const place of section.places) rows.push({ kind: 'place', place });
  }
  return rows;
}

export default function FeedScreen() {
  const router = useRouter();
  const selectedCity = useCityStore((s) => s.selectedCity);
  const { addSave, removeSave, isSaved } = useHitlistStore();
  const toast = useToast((s) => s.show);

  const [places, setPlaces] = useState<PlaceOut[]>([]);
  const [trending, setTrending] = useState<PlaceOut[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);
  const [error, setError] = useState(false);

  const loadingRef = useRef(false);
  const cancelledRef = useRef(false);

  const loadPage = useCallback(async (p: number, reset = false) => {
    if (loadingRef.current) return;
    if (!selectedCity) return;

    loadingRef.current = true;
    cancelledRef.current = false;
    if (!reset) setLoading(true);
    setError(false);

    try {
      const res = await fetchPlaces({ city_id: selectedCity.id, page: p, page_size: 40 });
      if (cancelledRef.current) return;
      setTotal(res.total);
      setPlaces((prev) => reset ? res.items : [...prev, ...res.items]);
      setPage(p);
    } catch {
      if (!cancelledRef.current) setError(true);
    } finally {
      if (!cancelledRef.current) {
        loadingRef.current = false;
        setLoading(false);
        setRefreshing(false);
        setInitialLoaded(true);
      }
    }
  }, [selectedCity]);

  useEffect(() => {
    cancelledRef.current = true;
    loadingRef.current = false;
    setPlaces([]);
    setPage(1);
    setInitialLoaded(false);
    setError(false);
    loadPage(1, true);
  }, [selectedCity?.id]);

  useEffect(() => {
    if (!selectedCity) return;
    fetchTrending(selectedCity.id).then(setTrending).catch(() => {});
  }, [selectedCity?.id]);

  const handleRefresh = () => { setRefreshing(true); loadPage(1, true); };
  const handleEndReached = () => {
    if (!loadingRef.current && places.length < total) loadPage(page + 1);
  };

  const rows = buildFeedRows(places);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>CRAVE</Text>
        {selectedCity && <Text style={styles.subtitle}>{selectedCity.name}</Text>}
      </View>

      <CitySelectorStrip />
      <TrendingStrip places={trending} onPress={(id) => router.push(`/place/${id}`)} />

      {!initialLoaded ? (
        <View style={styles.skeletonWrap}><SkeletonFeed count={4} /></View>
      ) : error ? (
        <ErrorState message="Couldn't load places" onRetry={() => loadPage(1, true)} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon="search-outline"
          title="Nothing here yet"
          body="Try selecting a different city"
        />
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(row, i) => row.kind === 'place' ? row.place.id : `header-${i}`}
          renderItem={({ item: row }) => {
            if (row.kind === 'header') {
              const tier = TIERS[row.tierKey];
              const count = rows.filter((r) => r.kind === 'place' && getTier(r.place.rank_score).key === row.tierKey).length;
              return <SectionHeader label={tier.sectionLabel} subtext={tier.sectionSubtext} count={count} />;
            }
            return (
              <PlaceCard
                place={row.place}
                onPress={() => router.push(`/place/${row.place.id}`)}
                onSave={() => {
                  if (isSaved(row.place.id)) {
                    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
                    removeSave(row.place.id);
                    toast('Removed from Hitlist');
                  } else {
                    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
                    addSave(row.place);
                    toast('Saved to Hitlist');
                  }
                }}
                saved={isSaved(row.place.id)}
              />
            );
          }}
          contentContainerStyle={styles.list}
          onEndReached={handleEndReached}
          onEndReachedThreshold={0.3}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={Colors.primary} />
          }
          ListFooterComponent={loading ? <ActivityIndicator color={Colors.primary} style={{ margin: 16 }} /> : null}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  list: { paddingHorizontal: 12, paddingBottom: 32, gap: 10 },
  skeletonWrap: { flex: 1, paddingHorizontal: 12, paddingTop: 10 },
  header: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 10,
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 8,
  },
  title: { fontSize: 28, fontWeight: '900', color: Colors.primary, letterSpacing: 2 },
  subtitle: { fontSize: 14, color: Colors.textSecondary, fontWeight: '500' },
});
```

- [ ] **Step 2: Verify**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: Feed screen — extracted components, error state, cancel ref, getTier fix, toast"
```

---

## Phase 2 — Interaction Polish

---

### Task 10: Extract ImageGallery + TrustBadgeRow, polish Detail screen

**Files:**
- Create: `src/components/ImageGallery.tsx`
- Create: `src/components/TrustBadgeRow.tsx`
- Modify: `app/place/[id].tsx`

- [ ] **Step 1: Create ImageGallery.tsx**

```typescript
// src/components/ImageGallery.tsx
import React, { useRef, useState } from 'react';
import { Dimensions, NativeScrollEvent, NativeSyntheticEvent, ScrollView, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { Colors } from '../constants/colors';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const GALLERY_HEIGHT = 280;
const FALLBACK = require('../../assets/icon.png');

interface Props {
  images: (string | null | undefined)[];
}

export function ImageGallery({ images }: Props) {
  const validImages = images.filter(Boolean) as string[];
  const sources = validImages.length > 0 ? validImages : [null];
  const [activeIndex, setActiveIndex] = useState(0);
  const scrollRef = useRef<ScrollView>(null);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const idx = Math.round(e.nativeEvent.contentOffset.x / SCREEN_WIDTH);
    setActiveIndex(idx);
  };

  return (
    <View style={styles.container}>
      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScroll={onScroll}
        scrollEventThrottle={16}
        decelerationRate="fast"
      >
        {sources.map((src, i) => (
          <Image
            key={i}
            source={src ?? FALLBACK}
            style={styles.image}
            contentFit="cover"
            placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
            transition={200}
          />
        ))}
      </ScrollView>
      {sources.length > 1 && (
        <View style={styles.dots}>
          {sources.map((_, i) => (
            <View key={i} style={[styles.dot, i === activeIndex && styles.dotActive]} />
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: 'relative' },
  image: { width: SCREEN_WIDTH, height: GALLERY_HEIGHT },
  dots: {
    position: 'absolute',
    bottom: 10,
    width: '100%',
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 5,
  },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.4)' },
  dotActive: { backgroundColor: Colors.text, width: 14, borderRadius: 3 },
});
```

- [ ] **Step 2: Create TrustBadgeRow.tsx**

```typescript
// src/components/TrustBadgeRow.tsx
import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { TrustBadge } from '../utils/scoring';

interface Props {
  badges: TrustBadge[];
}

export function TrustBadgeRow({ badges }: Props) {
  if (badges.length === 0) return null;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scroll}>
      {badges.map((b, i) => (
        <View key={i} style={[styles.badge, { backgroundColor: b.bg }]}>
          <Text style={[styles.label, { color: b.color }]}>{b.label}</Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingHorizontal: 16, gap: 8, paddingVertical: 4 },
  badge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    minHeight: 32,
    justifyContent: 'center',
  },
  label: { fontSize: 12, fontWeight: '700', letterSpacing: 0.3 },
});
```

- [ ] **Step 3: Replace app/place/[id].tsx**

```typescript
// app/place/[id].tsx
import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useLocalSearchParams, useNavigation } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { fetchPlaceDetail, PlaceOut } from '../../src/api/places';
import { getPlaceMenu, MenuItem } from '../../src/api/menu';
import { useHitlistStore } from '../../src/stores/hitlistStore';
import { useToast } from '../../src/hooks/useToast';
import { Colors } from '../../src/constants/colors';
import { getTier, getSignalContext, getTrustBadges } from '../../src/utils/scoring';
import { ImageGallery } from '../../src/components/ImageGallery';
import { TierBadge } from '../../src/components/TierBadge';
import { TrustBadgeRow } from '../../src/components/TrustBadgeRow';
import { ErrorState } from '../../src/components/ErrorState';

export default function PlaceDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const navigation = useNavigation();
  const { addSave, removeSave, isSaved } = useHitlistStore();
  const toast = useToast((s) => s.show);

  const [place, setPlace] = useState<PlaceOut | null>(null);
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [menuExpanded, setMenuExpanded] = useState(false);

  const load = () => {
    setLoading(true);
    setError(false);
    Promise.all([fetchPlaceDetail(id!), getPlaceMenu(id!).catch(() => [])])
      .then(([p, m]) => { setPlace(p); setMenuItems(m); navigation.setOptions({ title: p.name }); })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => { if (id) load(); }, [id]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={Colors.primary} size="large" />
      </View>
    );
  }

  if (error || !place) {
    return <ErrorState message="Couldn't load this place" onRetry={load} />;
  }

  const tier = getTier(place.rank_score);
  const context = getSignalContext(place);
  const badges = getTrustBadges(place);
  const saved = isSaved(place.id);
  const allImages = [place.primary_image_url, ...(place.images ?? [])];
  const previewMenu = menuExpanded ? menuItems : menuItems.slice(0, 5);

  // Group menu by category
  const menuByCategory: Record<string, MenuItem[]> = {};
  for (const item of previewMenu) {
    const cat = item.category ?? 'Menu';
    if (!menuByCategory[cat]) menuByCategory[cat] = [];
    menuByCategory[cat].push(item);
  }

  const handleSave = () => {
    Haptics.notificationAsync(
      saved ? Haptics.NotificationFeedbackType.Warning : Haptics.NotificationFeedbackType.Success,
    );
    if (saved) { removeSave(place.id); toast('Removed from Hitlist'); }
    else { addSave(place); toast('Saved to Hitlist'); }
  };

  const handleDirections = () => {
    if (!place.lat || !place.lng) return;
    const url = `maps://?q=${encodeURIComponent(place.name)}&ll=${place.lat},${place.lng}`;
    Linking.canOpenURL(url).then((ok) => {
      if (ok) Linking.openURL(url);
      else Linking.openURL(`https://maps.google.com/?q=${place.lat},${place.lng}`);
    });
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Hero */}
      <ImageGallery images={allImages} />

      {/* Identity block */}
      <View style={styles.identity}>
        <View style={styles.identityTop}>
          <TierBadge tier={tier} />
          {place.price_tier ? (
            <Text style={styles.price}>{'$'.repeat(place.price_tier)}</Text>
          ) : null}
        </View>
        <Text style={styles.name}>{place.name}</Text>
        <Text style={styles.meta}>
          {place.category ?? 'Restaurant'}
          {place.address ? `  ·  ${place.address}` : ''}
        </Text>
        <Text style={[styles.context, { color: tier.color }]}>{context}</Text>
      </View>

      {/* Trust badges */}
      <TrustBadgeRow badges={badges} />

      {/* Action row */}
      <View style={styles.actions}>
        <TouchableOpacity
          style={[styles.actionBtn, saved && styles.actionBtnActive]}
          onPress={handleSave}
          accessibilityLabel={saved ? 'Remove from Hitlist' : 'Save to Hitlist'}
          accessibilityRole="button"
        >
          <Ionicons name={saved ? 'bookmark' : 'bookmark-outline'} size={18} color={saved ? Colors.primary : Colors.text} />
          <Text style={[styles.actionLabel, saved && styles.actionLabelActive]}>
            {saved ? 'Saved' : 'Save'}
          </Text>
        </TouchableOpacity>

        {place.website ? (
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); Linking.openURL(place.website!); }}
            accessibilityLabel="Open website"
            accessibilityRole="link"
          >
            <Ionicons name="globe-outline" size={18} color={Colors.text} />
            <Text style={styles.actionLabel}>Website</Text>
          </TouchableOpacity>
        ) : null}

        {place.grubhub_url ? (
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); Linking.openURL(place.grubhub_url!); }}
            accessibilityLabel="Order online"
            accessibilityRole="link"
          >
            <Ionicons name="restaurant-outline" size={18} color={Colors.text} />
            <Text style={styles.actionLabel}>Order</Text>
          </TouchableOpacity>
        ) : null}

        {place.lat && place.lng ? (
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); handleDirections(); }}
            accessibilityLabel="Get directions"
            accessibilityRole="button"
          >
            <Ionicons name="navigate-outline" size={18} color={Colors.text} />
            <Text style={styles.actionLabel}>Directions</Text>
          </TouchableOpacity>
        ) : null}
      </View>

      {/* Menu */}
      <View style={styles.menuSection}>
        <Text style={styles.sectionTitle}>Menu</Text>
        {menuItems.length === 0 ? (
          <Text style={styles.noMenu}>
            {place.has_menu ? 'Loading menu…' : 'No menu on file yet'}
          </Text>
        ) : (
          <>
            {Object.entries(menuByCategory).map(([cat, items]) => (
              <View key={cat} style={styles.menuCategory}>
                <Text style={styles.menuCatLabel}>{cat}</Text>
                {items.map((item) => (
                  <View key={item.id} style={styles.menuItem}>
                    <View style={styles.menuItemMeta}>
                      <Text style={styles.menuItemName}>{item.name}</Text>
                      {item.description ? (
                        <Text style={styles.menuItemDesc} numberOfLines={2}>{item.description}</Text>
                      ) : null}
                    </View>
                    {item.price != null ? (
                      <Text style={styles.menuItemPrice}>${item.price.toFixed(2)}</Text>
                    ) : null}
                  </View>
                ))}
              </View>
            ))}
            {menuItems.length > 5 && (
              <TouchableOpacity
                style={styles.expandBtn}
                onPress={() => setMenuExpanded((v) => !v)}
                accessibilityRole="button"
              >
                <Text style={styles.expandLabel}>
                  {menuExpanded ? 'Show less' : `Show all ${menuItems.length} items`}
                </Text>
              </TouchableOpacity>
            )}
          </>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { paddingBottom: 40 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.background },
  identity: { padding: 16, gap: 5 },
  identityTop: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  price: { color: Colors.textSecondary, fontSize: 13, fontWeight: '600' },
  name: { fontSize: 24, fontWeight: '800', color: Colors.text, letterSpacing: 0.2 },
  meta: { fontSize: 14, color: Colors.textSecondary },
  context: { fontSize: 13, fontWeight: '600', marginTop: 2 },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: Colors.border,
    marginVertical: 8,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    minHeight: 44,
  },
  actionBtnActive: { borderColor: Colors.primary, backgroundColor: Colors.primary + '22' },
  actionLabel: { color: Colors.text, fontSize: 13, fontWeight: '600' },
  actionLabelActive: { color: Colors.primary },
  menuSection: { paddingHorizontal: 16, paddingTop: 8 },
  sectionTitle: { fontSize: 17, fontWeight: '800', color: Colors.text, marginBottom: 12, letterSpacing: 0.3 },
  noMenu: { color: Colors.textSecondary, fontSize: 14, paddingVertical: 8 },
  menuCategory: { marginBottom: 16 },
  menuCatLabel: {
    fontSize: 11,
    fontWeight: '800',
    color: Colors.textMuted,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  menuItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderColor: Colors.border,
  },
  menuItemMeta: { flex: 1 },
  menuItemName: { color: Colors.text, fontSize: 14, fontWeight: '600' },
  menuItemDesc: { color: Colors.textSecondary, fontSize: 12, marginTop: 2 },
  menuItemPrice: { color: Colors.textSecondary, fontSize: 14, fontWeight: '600', minWidth: 50, textAlign: 'right' },
  expandBtn: { marginTop: 8, paddingVertical: 12, alignItems: 'center' },
  expandLabel: { color: Colors.primary, fontSize: 14, fontWeight: '600' },
});
```

- [ ] **Step 4: Verify**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: ImageGallery, TrustBadgeRow, polished place detail with directions + expand menu"
```

---

### Task 11: Polish Hitlist screen

**Files:**
- Modify: `app/(tabs)/hitlist.tsx`

- [ ] **Step 1: Replace app/(tabs)/hitlist.tsx**

```typescript
// app/(tabs)/hitlist.tsx
import React from 'react';
import {
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useHitlistStore } from '../../src/stores/hitlistStore';
import { useToast } from '../../src/hooks/useToast';
import { Colors } from '../../src/constants/colors';
import { PlaceCardCompact } from '../../src/components/PlaceCardCompact';
import { EmptyState } from '../../src/components/EmptyState';

export default function HitlistScreen() {
  const router = useRouter();
  const { saves, removeSave } = useHitlistStore();
  const toast = useToast((s) => s.show);

  if (saves.length === 0) {
    return (
      <EmptyState
        icon="bookmark-outline"
        title="Your Hitlist is empty"
        body="Tap the bookmark on any place to save it here"
      />
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={saves}
        keyExtractor={(p) => p.id}
        renderItem={({ item }) => (
          <PlaceCardCompact
            place={item}
            onPress={() => router.push(`/place/${item.id}`)}
            rightAction={
              <TouchableOpacity
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                  removeSave(item.id);
                  toast('Removed from Hitlist');
                }}
                style={styles.removeBtn}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                accessibilityLabel={`Remove ${item.name} from hitlist`}
                accessibilityRole="button"
              >
                <Ionicons name="close" size={18} color={Colors.textMuted} />
              </TouchableOpacity>
            }
          />
        )}
        contentContainerStyle={styles.list}
        ListHeaderComponent={
          <Text style={styles.countLabel}>
            {saves.length} {saves.length === 1 ? 'place' : 'places'} saved
          </Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  list: { padding: 12, gap: 8, paddingBottom: 32 },
  countLabel: {
    color: Colors.textMuted,
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    paddingBottom: 10,
  },
  removeBtn: { padding: 8, minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
});
```

- [ ] **Step 2: Verify**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: Hitlist — PlaceCardCompact, fix copy, toast on remove"
```

---

### Task 12: Polish Search screen

**Files:**
- Modify: `app/(tabs)/search.tsx`

- [ ] **Step 1: Replace app/(tabs)/search.tsx**

```typescript
// app/(tabs)/search.tsx
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useCityStore } from '../../src/stores/cityStore';
import { searchPlaces } from '../../src/api/search';
import { fetchTrending, PlaceOut } from '../../src/api/places';
import { Colors } from '../../src/constants/colors';
import { PlaceCardCompact } from '../../src/components/PlaceCardCompact';
import { ErrorState } from '../../src/components/ErrorState';
import { EmptyState } from '../../src/components/EmptyState';

export default function SearchScreen() {
  const router = useRouter();
  const selectedCity = useCityStore((s) => s.selectedCity);

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PlaceOut[]>([]);
  const [trending, setTrending] = useState<PlaceOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [searched, setSearched] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!selectedCity) return;
    fetchTrending(selectedCity.id).then(setTrending).catch(() => {});
  }, [selectedCity?.id]);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim() || !selectedCity) {
      setResults([]);
      setSearched(false);
      return;
    }
    setLoading(true);
    setError(false);
    try {
      const data = await searchPlaces({ q, city_id: selectedCity.id, limit: 30 });
      setResults(data);
      setSearched(true);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [selectedCity]);

  const handleChange = (text: string) => {
    setQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(text), 350);
  };

  const handleClear = () => {
    setQuery('');
    setResults([]);
    setSearched(false);
    setError(false);
  };

  const showTrending = !searched && !loading && query.length === 0;
  const showNoResults = searched && !loading && results.length === 0 && !error;

  return (
    <View style={styles.container}>
      {/* Search bar */}
      <View style={styles.bar}>
        <View style={styles.inputRow}>
          <Ionicons name="search" size={16} color={Colors.textMuted} style={styles.searchIcon} />
          <TextInput
            style={styles.input}
            placeholder="Search places, cuisines…"
            placeholderTextColor={Colors.textMuted}
            value={query}
            onChangeText={handleChange}
            returnKeyType="search"
            onSubmitEditing={() => doSearch(query)}
            autoCorrect={false}
            accessibilityLabel="Search input"
          />
          {query.length > 0 && (
            <TouchableOpacity
              onPress={handleClear}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              accessibilityLabel="Clear search"
              accessibilityRole="button"
            >
              <Ionicons name="close-circle" size={18} color={Colors.textMuted} />
            </TouchableOpacity>
          )}
        </View>
        {selectedCity && (
          <Text style={styles.cityContext}>Searching in {selectedCity.name}</Text>
        )}
      </View>

      {/* Loading */}
      {loading && (
        <View style={styles.loadingRow}>
          <ActivityIndicator color={Colors.primary} size="small" />
        </View>
      )}

      {/* Error */}
      {error && !loading && (
        <ErrorState message="Search failed" onRetry={() => doSearch(query)} />
      )}

      {/* Trending empty state */}
      {showTrending && (
        <FlatList
          data={trending}
          keyExtractor={(p) => p.id}
          renderItem={({ item }) => (
            <PlaceCardCompact place={item} onPress={() => router.push(`/place/${item.id}`)} />
          )}
          contentContainerStyle={styles.list}
          ListHeaderComponent={
            trending.length > 0 ? <Text style={styles.sectionLabel}>TRENDING NOW</Text> : null
          }
        />
      )}

      {/* No results */}
      {showNoResults && (
        <EmptyState
          icon="search-outline"
          title="No results in this city"
          body="Try a different search term or browse the feed"
        />
      )}

      {/* Results */}
      {!showTrending && !showNoResults && !error && results.length > 0 && (
        <FlatList
          data={results}
          keyExtractor={(p) => p.id}
          renderItem={({ item }) => (
            <PlaceCardCompact place={item} onPress={() => router.push(`/place/${item.id}`)} />
          )}
          contentContainerStyle={styles.list}
          ListHeaderComponent={
            <Text style={styles.resultCount}>{results.length} result{results.length !== 1 ? 's' : ''}</Text>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  bar: { padding: 12, paddingBottom: 4, gap: 4 },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
    minHeight: 46,
  },
  searchIcon: { marginRight: 2 },
  input: { flex: 1, color: Colors.text, fontSize: 15 },
  cityContext: { color: Colors.textMuted, fontSize: 12, fontWeight: '500', paddingLeft: 4 },
  loadingRow: { paddingVertical: 20, alignItems: 'center' },
  list: { padding: 12, gap: 8, paddingBottom: 32 },
  sectionLabel: {
    color: Colors.textMuted,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.5,
    paddingBottom: 10,
  },
  resultCount: { color: Colors.textMuted, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', paddingBottom: 8 },
});
```

- [ ] **Step 2: Verify**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: Search — debounce, clear button, city label, PlaceCardCompact, trending empty state"
```

---

## Phase 3 — Map + Search Consistency

---

### Task 13: Fix Map screen — custom markers + bottom sheet

**Files:**
- Create: `src/components/MapMarker.tsx`
- Create: `src/components/MapBottomSheet.tsx`
- Modify: `app/(tabs)/map.tsx`

- [ ] **Step 1: Create MapMarker.tsx**

```typescript
// src/components/MapMarker.tsx
import React from 'react';
import { StyleSheet, View } from 'react-native';

interface Props {
  color: string;
  size?: number;
}

export function MapMarkerDot({ color, size = 14 }: Props) {
  return (
    <View style={[styles.outer, { borderColor: color, width: size + 8, height: size + 8, borderRadius: (size + 8) / 2 }]}>
      <View style={[styles.inner, { backgroundColor: color, width: size, height: size, borderRadius: size / 2 }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  outer: { borderWidth: 2, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(0,0,0,0.3)' },
  inner: {},
});
```

- [ ] **Step 2: Create MapBottomSheet.tsx**

```typescript
// src/components/MapBottomSheet.tsx
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../constants/colors';
import { TierBadge } from './TierBadge';
import { TrustLine } from './TrustLine';
import { getTier, getSignalContext } from '../utils/scoring';

interface FeatureProps {
  id: string;
  name: string;
  tier: string;
  image?: string;
  category?: string;
}

interface Props {
  feature: FeatureProps | null;
  onOpen: (id: string) => void;
  onClose: () => void;
}

// Map tier string (from GeoJSON) → TierKey
const TIER_MAP: Record<string, import('../utils/scoring').TierKey> = {
  elite:   'crave_pick',
  trusted: 'gem',
  solid:   'solid',
  default: 'new',
};

export function MapBottomSheet({ feature, onOpen, onClose }: Props) {
  if (!feature) return null;

  const tierKey = TIER_MAP[feature.tier] ?? 'new';
  const { getTier: _unused, ..._ } = { getTier: null };
  // Build a minimal PlaceOut for tier/context
  const fakeTier = require('../utils/scoring').TIERS[tierKey];

  return (
    <View style={styles.sheet}>
      <TouchableOpacity style={styles.closeBtn} onPress={onClose} accessibilityLabel="Close" accessibilityRole="button">
        <Ionicons name="close" size={18} color={Colors.textMuted} />
      </TouchableOpacity>
      <TouchableOpacity
        style={styles.row}
        onPress={() => onOpen(feature.id)}
        activeOpacity={0.85}
        accessibilityRole="button"
        accessibilityLabel={`Open ${feature.name}`}
      >
        {feature.image ? (
          <Image
            source={feature.image}
            style={styles.thumb}
            contentFit="cover"
            placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
          />
        ) : (
          <View style={[styles.thumb, styles.thumbFallback]}>
            <Ionicons name="restaurant" size={24} color={Colors.textMuted} />
          </View>
        )}
        <View style={styles.meta}>
          <TierBadge tier={fakeTier} />
          <Text style={styles.name} numberOfLines={1}>{feature.name}</Text>
          {feature.category ? <Text style={styles.category}>{feature.category}</Text> : null}
        </View>
        <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: Colors.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 16,
    paddingBottom: 32,
    borderTopWidth: 1,
    borderColor: Colors.border,
    shadowColor: '#000',
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: -4 },
    elevation: 16,
  },
  closeBtn: {
    position: 'absolute',
    top: 12,
    right: 16,
    padding: 6,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 8 },
  thumb: { width: 60, height: 60, borderRadius: 10 },
  thumbFallback: { backgroundColor: Colors.surfaceElevated, alignItems: 'center', justifyContent: 'center' },
  meta: { flex: 1, gap: 4 },
  name: { color: Colors.text, fontSize: 16, fontWeight: '700' },
  category: { color: Colors.textSecondary, fontSize: 13 },
});
```

- [ ] **Step 3: Replace app/(tabs)/map.tsx**

```typescript
// app/(tabs)/map.tsx
import React, { useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import MapView, { Marker, Region } from 'react-native-maps';
import { useRouter } from 'expo-router';
import { fetchMapGeoJSON, GeoJSONFeature } from '../../src/api/map';
import { useCityStore } from '../../src/stores/cityStore';
import { Colors, Colors as C } from '../../src/constants/colors';
import { CitySelectorStrip } from '../../src/components/CitySelectorStrip';
import { MapMarkerDot } from '../../src/components/MapMarker';
import { MapBottomSheet } from '../../src/components/MapBottomSheet';

// Map GeoJSON tier strings to canonical colors from colors.ts
const TIER_COLORS: Record<string, string> = {
  elite:   C.tierCravePick,
  trusted: C.tierGem,
  solid:   C.tierSolid,
  default: C.tierNew,
};

const DEFAULT_REGION: Region = {
  latitude: 37.8044,
  longitude: -122.2712,
  latitudeDelta: 0.08,
  longitudeDelta: 0.08,
};

function cityToRegion(lat: number, lng: number): Region {
  return { latitude: lat, longitude: lng, latitudeDelta: 0.08, longitudeDelta: 0.08 };
}

export default function MapScreen() {
  const router = useRouter();
  const selectedCity = useCityStore((s) => s.selectedCity);
  const mapRef = useRef<MapView>(null);

  const [features, setFeatures] = useState<GeoJSONFeature[]>([]);
  const [selectedFeature, setSelectedFeature] = useState<{
    id: string; name: string; tier: string; image?: string; category?: string;
  } | null>(null);

  useEffect(() => {
    if (!selectedCity) return;
    fetchMapGeoJSON({ city_id: selectedCity.id })
      .then((fc) => setFeatures(fc.features))
      .catch(() => {});
  }, [selectedCity?.id]);

  useEffect(() => {
    if (!selectedCity?.lat || !selectedCity?.lng) return;
    mapRef.current?.animateToRegion(cityToRegion(selectedCity.lat, selectedCity.lng), 500);
  }, [selectedCity?.id]);

  const initialRegion =
    selectedCity?.lat && selectedCity?.lng
      ? cityToRegion(selectedCity.lat, selectedCity.lng)
      : DEFAULT_REGION;

  return (
    <View style={styles.container}>
      <MapView ref={mapRef} style={styles.map} initialRegion={initialRegion} mapType="mutedStandard">
        {features.map((f) => {
          const [lng, lat] = f.geometry.coordinates;
          const tier = f.properties.tier as string;
          const color = TIER_COLORS[tier] ?? TIER_COLORS.default;
          return (
            <Marker
              key={f.properties.id}
              coordinate={{ latitude: lat, longitude: lng }}
              onPress={() => setSelectedFeature({
                id: f.properties.id,
                name: f.properties.name,
                tier,
                image: f.properties.image ?? undefined,
                category: f.properties.category ?? undefined,
              })}
              tracksViewChanges={false}
            >
              <MapMarkerDot color={color} />
            </Marker>
          );
        })}
      </MapView>

      {/* City selector strip overlaid at top */}
      <View style={styles.cityStrip}>
        <CitySelectorStrip />
      </View>

      {/* Bottom sheet */}
      <MapBottomSheet
        feature={selectedFeature}
        onOpen={(id) => router.push(`/place/${id}`)}
        onClose={() => setSelectedFeature(null)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  map: { flex: 1 },
  cityStrip: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    backgroundColor: Colors.background + 'EE',
  },
});
```

- [ ] **Step 4: Verify**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: Map — custom markers, bottom sheet on pin tap, city selector, unified tier colors"
```

---

## Phase 4 — Crave Loop + Final Polish

---

### Task 14: Hitlist Craves section

**Files:**
- Modify: `app/(tabs)/hitlist.tsx`

- [ ] **Step 1: Check if /api/v1/craves endpoint exists on the backend**

```bash
python3 -c "
from app.api.v1 import router
for r in router.routes:
    if hasattr(r, 'path') and 'crave' in r.path.lower():
        print(r.path, getattr(r, 'methods', ''))
" 2>/dev/null || grep -r "craves\|crave_item" /Users/angelowashington/CRAVE/backend/app/api --include="*.py" -l
```

- [ ] **Step 2: If the endpoint exists, add Craves section to hitlist.tsx**

Add after the imports in `app/(tabs)/hitlist.tsx`:

```typescript
import { useEffect, useState } from 'react';
import { getCraveItems, CraveItem } from '../../src/api/crave';
```

Add state inside the component:
```typescript
const [craves, setCraves] = useState<CraveItem[]>([]);

useEffect(() => {
  getCraveItems().then(setCraves).catch(() => {});
}, []);
```

Add Craves section after the saved list (above the closing `</View>`):

```typescript
{craves.length > 0 && (
  <View style={styles.cravesSection}>
    <Text style={styles.sectionLabel}>CRAVES</Text>
    {craves.map((item) => (
      <View key={item.id} style={styles.craveRow}>
        <View style={styles.craveMeta}>
          <Text style={styles.craveName} numberOfLines={1}>
            {item.parsed_place_name ?? item.url}
          </Text>
          <Text style={[styles.craveStatus, {
            color: item.matched_place_id ? Colors.success : Colors.textMuted
          }]}>
            {item.matched_place_id ? 'Matched' : 'Pending match'}
          </Text>
        </View>
        {item.matched_place_id && (
          <TouchableOpacity
            style={styles.craveOpenBtn}
            onPress={() => router.push(`/place/${item.matched_place_id}`)}
            accessibilityRole="button"
            accessibilityLabel={`Open matched place for ${item.parsed_place_name}`}
          >
            <Ionicons name="arrow-forward" size={16} color={Colors.primary} />
          </TouchableOpacity>
        )}
      </View>
    ))}
  </View>
)}
```

Add to StyleSheet:
```typescript
cravesSection: { padding: 12, paddingTop: 0 },
craveRow: {
  flexDirection: 'row',
  alignItems: 'center',
  padding: 12,
  backgroundColor: Colors.surface,
  borderRadius: 10,
  borderWidth: 1,
  borderColor: Colors.border,
  marginBottom: 8,
},
craveMeta: { flex: 1 },
craveName: { color: Colors.text, fontSize: 14, fontWeight: '600' },
craveStatus: { fontSize: 12, marginTop: 2 },
craveOpenBtn: { padding: 8, minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
```

- [ ] **Step 3: Add backend route if missing**

If `/api/v1/craves` doesn't exist, add it. Check:
```bash
grep -r "craves" /Users/angelowashington/CRAVE/backend/app/api --include="*.py" -l
```

If missing, create `app/api/v1/routes/craves.py`:
```python
# app/api/v1/routes/craves.py
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models.crave_item import CraveItem
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()

class CraveItemOut(BaseModel):
    id: str
    url: str
    source_type: str
    parsed_place_name: Optional[str]
    matched_place_id: Optional[str]
    match_confidence: Optional[float]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/craves", response_model=List[CraveItemOut])
def list_craves(db: Session = Depends(get_db)):
    return db.query(CraveItem).order_by(CraveItem.created_at.desc()).limit(50).all()
```

Then register in `app/api/v1/__init__.py` or `app/api/v1/router.py` — find where other routes are registered and add:
```python
from app.api.v1.routes.craves import router as craves_router
api_router.include_router(craves_router, prefix="/api/v1")
```

- [ ] **Step 4: Verify**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "feat: Hitlist Craves section — shows imported items with match status"
```

---

### Task 15: Remove NativeWind + final cleanup

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Remove unused deps from package.json**

Edit `frontend/package.json`. Remove from `"dependencies"`:
- `"nativewind": "^4.2.3"`
- `"tailwindcss": "^4.2.2"`

- [ ] **Step 2: Remove node_modules entries**

```bash
cd /Users/angelowashington/CRAVE/frontend && npm uninstall nativewind tailwindcss
```

- [ ] **Step 3: Final TypeScript check**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx tsc --noEmit
```
Expected: zero errors.

- [ ] **Step 4: Verify Expo can start**

```bash
cd /Users/angelowashington/CRAVE/frontend && npx expo export --platform ios --dev 2>&1 | tail -5
```
Expected: no fatal errors (warnings about missing Metro config are OK).

- [ ] **Step 5: Final commit**

```bash
git -C /Users/angelowashington/CRAVE add -A && git -C /Users/angelowashington/CRAVE commit -m "chore: remove unused nativewind/tailwind, final cleanup"
```

---

## Acceptance Criteria

Run through each check manually in Expo Go after all tasks are complete:

- [ ] Feed opens → CRAVE Picks at top, section subtext visible, cards show trust lines in tier color
- [ ] City selector switches city → feed reloads, no blank flash
- [ ] Network failure on feed → ErrorState shown with retry button
- [ ] Tap any card → detail opens with gallery, tier badge, action row, directions button
- [ ] Tap save on card → Toast "Saved to Hitlist" + bookmark fills in
- [ ] Tap save again → Toast "Removed from Hitlist" + bookmark clears
- [ ] Search: type query → debounced results appear, city label visible, clear button works
- [ ] Search: empty state shows trending places before any query
- [ ] Map: pins are colored dots by tier, tapping pin opens bottom sheet, city selector visible at top
- [ ] Map: bottom sheet tap opens detail screen (works on both iOS and Android)
- [ ] Hitlist: shows saved places with PlaceCardCompact, remove button works, correct empty state copy
- [ ] Detail: menu expandable, "Show all N items" visible, directions button opens maps app
- [ ] App chrome (status bar, keyboard) is dark on both platforms
- [ ] `npx tsc --noEmit` passes with zero errors
