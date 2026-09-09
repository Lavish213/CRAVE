import React from 'react';
import { StyleSheet, View } from 'react-native';
import { uiColors, uiRadius, uiSpace } from '../tokens';
import { CraveButton, CraveText } from '../primitives';
import { FoodMedia } from './FoodMedia';
import { OperationalStatus, type OperationalState } from './OperationalStatus';

export interface MapPlaceCardProps {
  name: string;
  image?: string | null;
  category?: string | null;
  distanceLabel?: string | null;
  operationalState?: OperationalState;
  saved?: boolean;
  onOpen: () => void;
  onSave?: () => void;
  onDirections?: () => void;
}

export function MapPlaceCard({ name, image, category, distanceLabel, operationalState, saved = false, onOpen, onSave, onDirections }: MapPlaceCardProps) {
  const meta = [category, distanceLabel].filter(Boolean).join('  ·  ');

  return (
    <View style={styles.card}>
      <View style={styles.identityRow}>
        <FoodMedia source={image} placeName={name} variant="compact" />
        <View style={styles.copy}>
          <CraveText role="subtitle" numberOfLines={3}>{name}</CraveText>
          {meta ? <CraveText role="caption" tone="secondary">{meta}</CraveText> : null}
          {operationalState ? <OperationalStatus state={operationalState} compact /> : null}
        </View>
      </View>
      <View style={styles.actions}>
        {onDirections ? <CraveButton label="Directions" variant="primary" onPress={onDirections} style={styles.action} /> : null}
        {onSave ? <CraveButton label={saved ? 'Saved' : 'Save'} variant="secondary" onPress={onSave} disabled={saved} style={styles.action} /> : null}
      </View>
      <CraveButton label="View place" variant="ghost" onPress={onOpen} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: uiColors.surface.overlay,
    borderRadius: uiRadius.card,
    gap: uiSpace.md,
  },
  identityRow: {
    flexDirection: 'row',
    gap: uiSpace.md,
  },
  copy: {
    flex: 1,
    gap: uiSpace.xs,
  },
  actions: {
    flexDirection: 'row',
    gap: uiSpace.sm,
  },
  action: {
    flex: 1,
  },
});
