import React from 'react';
import { CraveButton } from '../primitives';

export interface SaveActionProps {
  saved: boolean;
  loading?: boolean;
  onPress: () => void;
}

export function SaveAction({ saved, loading = false, onPress }: SaveActionProps) {
  return (
    <CraveButton
      label={saved ? 'Saved' : 'Save'}
      variant={saved ? 'secondary' : 'primary'}
      disabled={saved}
      loading={loading}
      onPress={onPress}
      accessibilityLabel={saved ? 'Saved to Craves' : 'Save to Craves'}
    />
  );
}
