import React from 'react';
import {
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  ViewStyle,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius, Spacing } from '../constants/colors';
import { PlaceOut } from '../api/places';
import { formatDistance, formatPrice } from '../utils/scoring';

export function V2Screen({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[styles.screen, style]}>{children}</View>;
}

export function V2Glow() {
  return (
    <>
      <View pointerEvents="none" style={[styles.glow, styles.glowGold]} />
      <View pointerEvents="none" style={[styles.glow, styles.glowGreen]} />
    </>
  );
}

export function V2TopBar({
  location,
  right,
}: {
  location?: string;
  right?: React.ReactNode;
}) {
  return (
    <View style={styles.topBar}>
      <View>
        <Text style={styles.wordmark}>CRAVE</Text>
        {location ? (
          <Text style={styles.location}>
            <Ionicons name="location" size={12} color={Colors.craveGold} /> {location}
          </Text>
        ) : null}
      </View>
      {right}
    </View>
  );
}

export function V2BrandLine({ children = 'Real food. Real places. Right now.' }: { children?: string }) {
  return <Text style={styles.brandLine}>{children}</Text>;
}

export function V2Chip({
  label,
  tone = 'neutral',
  icon,
}: {
  label: string;
  tone?: 'neutral' | 'selected' | 'good' | 'warn';
  icon?: React.ComponentProps<typeof Ionicons>['name'];
}) {
  const toneStyle =
    tone === 'selected'
      ? styles.chipSelected
      : tone === 'good'
        ? styles.chipGood
        : tone === 'warn'
          ? styles.chipWarn
          : null;
  return (
    <View style={[styles.chip, toneStyle]}>
      {icon ? (
        <Ionicons
          name={icon}
          size={12}
          color={tone === 'selected' ? Colors.craveGold : Colors.craveMuted}
        />
      ) : null}
      <Text style={[styles.chipText, tone === 'selected' ? styles.chipTextSelected : null]}>
        {label}
      </Text>
    </View>
  );
}

export function V2Button({
  label,
  onPress,
  variant = 'primary',
  icon,
}: {
  label: string;
  onPress?: () => void;
  variant?: 'primary' | 'secondary';
  icon?: React.ComponentProps<typeof Ionicons>['name'];
}) {
  return (
    <TouchableOpacity
      style={[styles.button, variant === 'secondary' ? styles.buttonSecondary : styles.buttonPrimary]}
      onPress={onPress}
      disabled={!onPress}
      activeOpacity={0.82}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      {icon ? (
        <Ionicons
          name={icon}
          size={16}
          color={variant === 'primary' ? Colors.craveInk : Colors.craveCream}
        />
      ) : null}
      <Text style={[styles.buttonText, variant === 'secondary' ? styles.buttonSecondaryText : null]}>
        {label}
      </Text>
    </TouchableOpacity>
  );
}

export function V2Hero({
  title,
  subtitle,
  image,
  children,
}: {
  title: string;
  subtitle?: string;
  image?: string | null;
  children?: React.ReactNode;
}) {
  return (
    <View style={styles.hero}>
      {image ? (
        <Image
          source={image}
          style={StyleSheet.absoluteFill}
          contentFit="cover"
          transition={180}
          cachePolicy="memory-disk"
        />
      ) : (
        <View style={styles.heroFallback}>
          <Ionicons name="restaurant-outline" size={44} color={Colors.craveGold} />
          <Text style={styles.heroFallbackText}>CRAVE</Text>
        </View>
      )}
      <View style={styles.heroScrim} />
      <View style={styles.heroContent}>
        <Text style={styles.heroTitle}>{title}</Text>
        {subtitle ? <Text style={styles.heroSubtitle}>{subtitle}</Text> : null}
        {children}
      </View>
    </View>
  );
}

export function v2PlaceImage(place?: PlaceOut | null): string | null {
  return place?.primary_image_url ?? place?.image ?? place?.images?.[0] ?? null;
}

export function v2PlaceMeta(place: PlaceOut): string {
  const distance = formatDistance(place.distance_miles);
  const price = place.price ?? formatPrice(place);
  const parts = [
    distance,
    place.hours_status === 'open' ? 'Open now' : place.hours_status === 'closed' ? 'Closed now' : null,
    price,
  ].filter(Boolean);
  return parts.join(' · ');
}

export function V2PlaceFallback({ name, height = 156 }: { name: string; height?: number }) {
  return (
    <View style={[styles.placeFallback, { height }]}>
      <Ionicons name="restaurant-outline" size={30} color={Colors.craveGold} />
      <Text style={styles.placeFallbackText}>{name}</Text>
      <Text style={styles.placeFallbackSub}>Photo unavailable</Text>
    </View>
  );
}

export function V2PlaceCard({
  place,
  label,
  reason,
  onPress,
  onPressIn,
  onSave,
  saved,
  compact = false,
  style,
}: {
  place: PlaceOut;
  label?: string;
  reason?: string;
  onPress: () => void;
  onPressIn?: () => void;
  onSave?: () => void;
  saved?: boolean;
  compact?: boolean;
  style?: ViewStyle;
}) {
  const image = v2PlaceImage(place);
  const category = place.category ?? place.categories?.[0] ?? 'Restaurant';
  return (
    <View
      style={[compact ? styles.compactCard : styles.placeCard, style]}
    >
      <TouchableOpacity
        style={compact ? styles.compactCardPressable : styles.placeCardPressable}
        onPress={onPress}
        onPressIn={onPressIn}
        activeOpacity={0.86}
        accessibilityRole="button"
        accessibilityLabel={`${place.name}, ${category}`}
      >
        <View style={compact ? styles.compactImageWrap : styles.placeImageWrap}>
          {image ? (
            <Image
              source={image}
              style={compact ? styles.compactImage : styles.placeImage}
              contentFit="cover"
              transition={160}
              cachePolicy="memory-disk"
            />
          ) : (
            <V2PlaceFallback name={place.name} height={compact ? 72 : 190} />
          )}
          {label ? (
            <View style={styles.placeLabel}>
              <Text style={styles.placeLabelText}>{label}</Text>
            </View>
          ) : null}
        </View>
        <View style={compact ? styles.compactBody : styles.placeBody}>
          <View style={styles.placeTitleRow}>
            <Text style={compact ? styles.compactName : styles.placeName} numberOfLines={compact ? 1 : 2}>
              {place.name}
            </Text>
            {onSave ? <View style={styles.saveButtonSpacer} /> : null}
          </View>
          <Text style={styles.placeMeta} numberOfLines={1}>{v2PlaceMeta(place)}</Text>
          {reason ? <Text style={styles.placeReason} numberOfLines={compact ? 2 : 3}>{reason}</Text> : null}
          {!compact ? (
            <View style={styles.chipRow}>
              <V2Chip label={category} icon="restaurant-outline" />
              {place.price ? <V2Chip label={place.price} icon="cash-outline" /> : null}
              {place.outdoor_seating === 'yes' ? <V2Chip label="Outdoor" icon="leaf-outline" tone="good" /> : null}
            </View>
          ) : null}
        </View>
      </TouchableOpacity>
      {onSave ? (
        <TouchableOpacity
          style={compact ? styles.compactSaveButton : styles.saveButton}
          onPress={onSave}
          accessibilityRole="button"
          accessibilityLabel={saved ? `Remove ${place.name} from saves` : `Save ${place.name}`}
        >
          <Ionicons
            name={saved ? 'heart' : 'heart-outline'}
            size={compact ? 20 : 24}
            color={saved ? Colors.craveGold : Colors.craveCream}
          />
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.craveInk,
  },
  glow: {
    position: 'absolute',
    width: 220,
    height: 220,
    borderRadius: 110,
    opacity: 0.24,
  },
  glowGold: {
    right: -90,
    top: 60,
    backgroundColor: Colors.craveGoldDeep,
  },
  glowGreen: {
    left: -120,
    bottom: 120,
    backgroundColor: '#123B32',
  },
  topBar: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  wordmark: {
    color: Colors.craveCream,
    fontSize: 26,
    fontWeight: '900',
    letterSpacing: 1.8,
  },
  location: {
    color: Colors.craveMuted,
    fontSize: 12,
    fontWeight: '700',
    marginTop: 2,
  },
  brandLine: {
    color: Colors.craveMuted,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.8,
    textTransform: 'uppercase',
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    minHeight: 32,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: Radius.full,
    borderWidth: 1,
    borderColor: 'rgba(247,239,228,0.14)',
    backgroundColor: 'rgba(247,239,228,0.055)',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  chipSelected: {
    borderColor: 'rgba(255,180,92,0.48)',
    backgroundColor: 'rgba(255,180,92,0.14)',
  },
  chipGood: {
    borderColor: 'rgba(127,216,154,0.35)',
    backgroundColor: 'rgba(127,216,154,0.10)',
  },
  chipWarn: {
    borderColor: 'rgba(255,180,92,0.45)',
    backgroundColor: 'rgba(255,180,92,0.10)',
  },
  chipText: {
    color: Colors.craveCream,
    fontSize: 12,
    fontWeight: '700',
  },
  chipTextSelected: {
    color: Colors.craveGold,
  },
  button: {
    minHeight: 48,
    borderRadius: Radius.full,
    paddingHorizontal: 18,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  buttonPrimary: {
    backgroundColor: Colors.craveCream,
  },
  buttonSecondary: {
    borderWidth: 1,
    borderColor: 'rgba(247,239,228,0.18)',
    backgroundColor: 'rgba(247,239,228,0.06)',
  },
  buttonText: {
    color: Colors.craveInk,
    fontSize: 14,
    fontWeight: '900',
  },
  buttonSecondaryText: {
    color: Colors.craveCream,
  },
  hero: {
    minHeight: 390,
    marginHorizontal: Spacing.md,
    borderRadius: 28,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(247,239,228,0.15)',
    justifyContent: 'flex-end',
  },
  heroFallback: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.craveSurface,
    gap: Spacing.sm,
  },
  heroFallbackText: {
    color: Colors.craveCream,
    fontSize: 18,
    fontWeight: '900',
    letterSpacing: 4,
  },
  heroScrim: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.38)',
  },
  heroContent: {
    padding: Spacing.lg,
    gap: Spacing.md,
  },
  heroTitle: {
    color: Colors.craveCream,
    fontSize: 42,
    lineHeight: 43,
    fontWeight: '900',
    letterSpacing: -1.2,
  },
  heroSubtitle: {
    color: Colors.craveCream,
    fontSize: 14,
    lineHeight: 20,
    fontWeight: '700',
  },
  placeCard: {
    borderRadius: 24,
    overflow: 'hidden',
    backgroundColor: 'rgba(16,26,24,0.88)',
    borderWidth: 1,
    borderColor: 'rgba(247,239,228,0.14)',
  },
  placeCardPressable: {
    flex: 1,
  },
  compactCard: {
    borderRadius: 18,
    backgroundColor: 'rgba(16,26,24,0.84)',
    borderWidth: 1,
    borderColor: 'rgba(247,239,228,0.12)',
  },
  compactCardPressable: {
    flexDirection: 'row',
    gap: 12,
    padding: 10,
  },
  placeImageWrap: {
    minHeight: 156,
    backgroundColor: Colors.craveSurface2,
  },
  compactImageWrap: {
    width: 86,
    height: 72,
    borderRadius: 14,
    overflow: 'hidden',
    backgroundColor: Colors.craveSurface2,
  },
  placeImage: {
    width: '100%',
    height: 190,
  },
  compactImage: {
    width: '100%',
    height: '100%',
  },
  placeLabel: {
    position: 'absolute',
    left: 12,
    top: 12,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: Radius.full,
    backgroundColor: 'rgba(6,13,12,0.72)',
    borderWidth: 1,
    borderColor: 'rgba(255,180,92,0.38)',
  },
  placeLabelText: {
    color: Colors.craveCream,
    fontSize: 12,
    fontWeight: '900',
  },
  placeBody: {
    padding: Spacing.md,
    gap: Spacing.sm,
  },
  compactBody: {
    flex: 1,
    gap: 4,
    paddingRight: 34,
  },
  placeTitleRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 10,
  },
  placeName: {
    flex: 1,
    color: Colors.craveCream,
    fontSize: 24,
    lineHeight: 28,
    fontWeight: '900',
    letterSpacing: -0.35,
  },
  compactName: {
    flex: 1,
    color: Colors.craveCream,
    fontSize: 17,
    fontWeight: '900',
  },
  saveButton: {
    position: 'absolute',
    right: 10,
    top: 198,
    minWidth: 44,
    minHeight: 44,
    borderRadius: Radius.full,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(6,13,12,0.42)',
  },
  compactSaveButton: {
    position: 'absolute',
    right: 6,
    top: 6,
    minWidth: 44,
    minHeight: 44,
    borderRadius: Radius.full,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveButtonSpacer: {
    width: 34,
  },
  placeMeta: {
    color: Colors.craveMuted,
    fontSize: 13,
    fontWeight: '700',
  },
  placeReason: {
    color: Colors.craveCream,
    fontSize: 14,
    lineHeight: 20,
  },
  placeFallback: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#2A1E17',
    gap: 6,
    paddingHorizontal: Spacing.md,
  },
  placeFallbackText: {
    color: Colors.craveCream,
    fontSize: 18,
    fontWeight: '900',
    textAlign: 'center',
  },
  placeFallbackSub: {
    color: Colors.craveMuted,
    fontSize: 12,
    fontWeight: '700',
  },
});
