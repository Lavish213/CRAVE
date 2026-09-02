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
import { MissingMediaState } from './MissingMediaState';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const GALLERY_HEIGHT = 280;
// Materially shorter than GALLERY_HEIGHT -- an empty hero must not
// reserve the same giant vertical space a real photo would.
const NO_PHOTOS_HEIGHT = 120;

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

  // Honest, compact empty state -- previously reserved the exact same
  // GALLERY_HEIGHT a real photo hero would, which wastes most of the
  // screen's top on nothing. Shares MissingMediaState with PlaceCard's
  // identical situation rather than each maintaining its own copy.
  if (!hasPhotos) {
    return (
      <MissingMediaState
        height={NO_PHOTOS_HEIGHT}
        accessibilityLabel={placeName ? `No photos yet for ${placeName}` : 'No photos yet'}
      />
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
