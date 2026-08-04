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
}

export function ImageGallery({ images, gpsVerified }: Props) {
  // Paired and filtered together so a dropped null image can't shift a
  // later flag onto the wrong photo.
  const pairs = images
    .map((src, i) => ({ src, verified: !!gpsVerified?.[i] }))
    .filter((p): p is { src: string; verified: boolean } => !!p.src);

  const sources = pairs.length > 0 ? pairs : [{ src: null as string | null, verified: false }];
  const [activeIndex, setActiveIndex] = useState(0);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const idx = Math.round(e.nativeEvent.contentOffset.x / SCREEN_WIDTH);
    setActiveIndex(idx);
  };

  return (
    <View>
      <ScrollView
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScroll={onScroll}
        scrollEventThrottle={16}
        decelerationRate="fast"
      >
        {sources.map((item, i) => (
          <View key={i}>
            <Image
              // Full-bleed hero — opt up from the proxy's thumbnail-sized
              // default, which is tuned for feed cards, not a screen-width image.
              source={withImageWidth(item.src, MAX_IMAGE_WIDTH) ?? require('../../assets/icon.png')}
              style={styles.image}
              contentFit="cover"
              placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
              transition={200}
            />
            {item.verified ? (
              <View style={styles.verifiedBadge}>
                <Ionicons name="location" size={12} color={Colors.text} />
                <Text style={styles.verifiedText}>Verified visit</Text>
              </View>
            ) : null}
          </View>
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
