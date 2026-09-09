import React from 'react';
import { StyleSheet, View } from 'react-native';
import { uiSpace } from '../tokens';
import { CraveText } from '../primitives';

export interface InterpretationLineProps {
  query: string;
  uncertain?: boolean;
}

export function InterpretationLine({ query, uncertain = false }: InterpretationLineProps) {
  return (
    <View style={styles.container}>
      <CraveText role="micro" tone={uncertain ? 'uncertain' : 'brand'}>
        {uncertain ? 'CHECK THIS SEARCH' : 'UNDERSTOOD'}
      </CraveText>
      <CraveText role="body">Searching for {query}</CraveText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: uiSpace.xs,
  },
});
