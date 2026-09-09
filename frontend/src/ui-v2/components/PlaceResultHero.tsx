import React from 'react';
import { StyleSheet, View } from 'react-native';
import type { PlaceOut } from '../../api/places';
import { formatDistance, formatPrice } from '../../utils/scoring';
import { uiColors, uiElevation, uiRadius, uiSpace } from '../tokens';
import { CravePressable, CraveText } from '../primitives';
import { FoodMedia } from './FoodMedia';
import { ReasonLine, type ReasonKind } from './ReasonLine';
import { ConfidenceStatement, type PersonalizationConfidence } from './ConfidenceStatement';
import { OperationalStatus, type OperationalState } from './OperationalStatus';
import { EvidenceLimitation, type EvidenceLimitationKind } from './EvidenceLimitation';

export interface PlaceResultHeroProps {
  place: PlaceOut;
  onPress: () => void;
  onPressIn?: () => void;
  reasonKind?: ReasonKind;
  reason?: string | null;
  confidence?: PersonalizationConfidence;
  operationalState?: OperationalState;
  operationalDetail?: string | null;
  limitation?: EvidenceLimitationKind;
  action?: React.ReactNode;
}

function placeMeta(place: PlaceOut): string[] {
  return [
    place.category,
    place.price ?? formatPrice(place),
    formatDistance(place.distance_miles),
  ].filter((value): value is string => Boolean(value));
}

export function PlaceResultHero({
  place,
  onPress,
  onPressIn,
  reasonKind,
  reason,
  confidence,
  operationalState,
  operationalDetail,
  limitation,
  action,
}: PlaceResultHeroProps) {
  const metadata = placeMeta(place);

  return (
    <View style={styles.card}>
      <CravePressable
        onPress={onPress}
        onPressIn={onPressIn}
        accessibilityLabel={`${place.name}${place.category ? `, ${place.category}` : ''}`}
        style={styles.contentPressable}
      >
        <FoodMedia source={place.image ?? place.primary_image_url} placeName={place.name} variant="hero" />
        <View style={styles.copy}>
          <CraveText role="headline" numberOfLines={3}>{place.name}</CraveText>
          {metadata.length > 0 ? <CraveText role="body" tone="secondary">{metadata.join('  ·  ')}</CraveText> : null}
          <ReasonLine kind={reasonKind} reason={reason} />
          {confidence ? <ConfidenceStatement confidence={confidence} /> : null}
          {operationalState ? <OperationalStatus state={operationalState} detail={operationalDetail} /> : null}
          {limitation ? <EvidenceLimitation kind={limitation} /> : null}
        </View>
      </CravePressable>
      {action ? <View style={styles.action}>{action}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: uiColors.surface.primary,
    borderRadius: uiRadius.card,
    borderWidth: 1,
    borderColor: uiColors.border.subtle,
    overflow: 'hidden',
    ...uiElevation.card,
  },
  contentPressable: {
    gap: uiSpace.md,
  },
  copy: {
    paddingHorizontal: uiSpace.cardInset,
    gap: uiSpace.sm,
  },
  action: {
    padding: uiSpace.cardInset,
    paddingTop: uiSpace.md,
  },
});
