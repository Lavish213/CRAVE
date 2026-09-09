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

export interface PlaceResultSupportingProps {
  place: PlaceOut;
  onPress: () => void;
  onPressIn?: () => void;
  reasonKind?: ReasonKind;
  reason?: string | null;
  confidence?: PersonalizationConfidence;
  operationalState?: OperationalState;
  limitation?: EvidenceLimitationKind;
  action?: React.ReactNode;
}

export function PlaceResultSupporting({ place, onPress, onPressIn, reasonKind, reason, confidence, operationalState, limitation, action }: PlaceResultSupportingProps) {
  const metadata = [place.category, place.price ?? formatPrice(place), formatDistance(place.distance_miles)]
    .filter((value): value is string => Boolean(value));

  return (
    <View style={styles.card}>
      <CravePressable onPress={onPress} onPressIn={onPressIn} accessibilityLabel={`${place.name}${place.category ? `, ${place.category}` : ''}`} style={styles.pressable}>
        <FoodMedia source={place.image ?? place.primary_image_url} placeName={place.name} variant="compact" />
        <View style={styles.copy}>
          <CraveText role="subtitle" numberOfLines={3}>{place.name}</CraveText>
          {metadata.length > 0 ? <CraveText role="caption" tone="secondary" numberOfLines={2}>{metadata.join('  ·  ')}</CraveText> : null}
          <ReasonLine kind={reasonKind} reason={reason} compact />
          {confidence ? <ConfidenceStatement confidence={confidence} compact /> : null}
          {operationalState ? <OperationalStatus state={operationalState} compact /> : null}
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
    ...uiElevation.card,
  },
  pressable: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: uiSpace.md,
    padding: uiSpace.md,
  },
  copy: {
    flex: 1,
    gap: uiSpace.xs,
  },
  action: {
    paddingHorizontal: uiSpace.md,
    paddingBottom: uiSpace.md,
  },
});
