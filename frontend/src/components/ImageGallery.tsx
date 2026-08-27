// src/components/ImageGallery.tsx
import React, { useRef, useState } from 'react';
import {
  Dimensions,
  NativeScrollEvent,
  NativeSyntheticEvent,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Radius, Spacing } from '../constants/colors';
import { MAX_IMAGE_WIDTH, withImageWidth } from '../utils/imageUrl';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const GALLERY_HEIGHT = 280;

interface Props {
  images: (string | null | undefined)[];
  /**
   * Index-aligned with `images` (before filtering). EXIF GPS on the photo
   * matched the place's own coordinates at upload time — see
   * app/services/images/exif_reader.py — computed and stored server-side
   * since that pass shipped, but never surfaced anywhere until now.
   */
  gpsVerified?: (boolean | null | undefined)[];
  /** For accessibility labels ("Photo 1 of 3 for Nari") and the empty
   * state's fallback initial. Optional so existing callers that predate
   * this don't break; falls back to generic wording without it. */
  placeName?: string;
}

export function ImageGallery({ images, gpsVerified, placeName }: Props) {
  // Paired and filtered together so a dropped null image can't shift a
  // later flag onto the wrong photo.
  const pairs = images
    .map((src, i) => ({ src, verified: !!gpsVerified?.[i] }))
    .filter((p): p is { src: string; verified: boolean } => !!p.src);

  const hasPhotos = pairs.length > 0;
  const [activeIndex, setActiveIndex] = useState(0);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const idx = Math.round(e.nativeEvent.contentOffset.x / SCREEN_WIDTH);
    setActiveIndex(idx);
  };

  // Honest empty state -- previously stretched the app's own icon
  // full-bleed as a stand-in photo, which reads as a broken/wrong image
  // rather than a designed "no photos yet" state. Mirrors PlaceCard's
  // existing fallback (initial letter + category-style muted panel)
  // instead of inventing a new visual language for the same situation.
  if (!hasPhotos) {
    return (
      <View
        style={[styles.image, styles.noPhotos]}
        accessible
        accessibilityLabel={placeName ? `No photos yet for ${placeName}` : 'No photos yet'}
      >
        <Ionicons name="camera-outline" size={40} color={Colors.textSecondary} />
        <Text style={styles.noPhotosText}>No photos yet</Text>
      </View>
    );
  }

  return (
    <View>
      <ScrollView
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScroll={onScroll}
        scrollEventThrottle={16}
        decelerationRate="fast"
        accessibilityRole="adjustable"
        accessibilityLabel={placeName ? `Photos of ${placeName}` : 'Photos'}
        accessibilityHint={pairs.length > 1 ? 'Swipe to see more photos' : undefined}
      >
        {pairs.map((item, i) => (
          <View key={i}>
            <Image
              // Full-bleed hero — opt up from the proxy's thumbnail-sized
              // default, which is tuned for feed cards, not a screen-width image.
              source={withImageWidth(item.src, MAX_IMAGE_WIDTH)}
              style={styles.image}
              contentFit="cover"
              placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
              transition={200}
              cachePolicy="memory-disk"
              accessible
              accessibilityLabel={
                `Photo ${i + 1} of ${pairs.length}${placeName ? ` for ${placeName}` : ''}` +
                (item.verified ? ', verified visit' : '')
              }
            />
            {item.verified ? (
              <View style={styles.verifiedBadge} importantForAccessibility="no">
                <Ionicons name="location" size={12} color={Colors.text} />
                <Text style={styles.verifiedText}>Verified visit</Text>
              </View>
            ) : null}
          </View>
        ))}
      </ScrollView>
      {pairs.length > 1 && (
        <View style={styles.dots} importantForAccessibility="no">
          {pairs.map((_, i) => (
            <View key={i} style={[styles.dot, i === activeIndex && styles.dotActive]} />
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  image: { width: SCREEN_WIDTH, height: GALLERY_HEIGHT },
  noPhotos: {
    backgroundColor: Colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
  },
  // textSecondary, not textMuted -- textMuted on this background computes
  // to roughly 2:1 contrast, well under WCAG AA's 4.5:1 for normal text
  // (a real, pre-existing, app-wide gap -- see CRAVE_REMAINING_WORK.md).
  // Not introducing a new instance of it here.
  noPhotosText: { color: Colors.textSecondary, fontSize: 13, fontWeight: '600' },
  verifiedBadge: {
    position: 'absolute',
    top: Spacing.md,
    left: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: Radius.pill,
    backgroundColor: 'rgba(0,0,0,0.55)',
  },
  verifiedText: { color: Colors.text, fontSize: 11, fontWeight: '700' },
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
