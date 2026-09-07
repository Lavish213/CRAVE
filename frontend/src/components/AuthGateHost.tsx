import React, { Suspense, useCallback } from 'react';
import { supabase } from '../lib/supabase';
import { useToast } from '../hooks/useToast';
import {
  cancelAuthGate,
  resumePendingAuthAction,
  useAuthGateStore,
  type AuthGateReason,
} from '../stores/authGateStore';

// AuthSheet constructs OAuth helpers from Expo modules. Keep that dependency
// out of the root-layout import path until the gate is actually visible; this
// also avoids paying the OAuth module cost on ordinary app startup.
const LazyAuthSheet = React.lazy(async () => {
  const module = await import('./AuthSheet');
  return { default: module.AuthSheet };
});

type AuthSheetReason = 'save' | 'craves' | 'profile' | 'add-spot' | 'default';

function authSheetReason(reason: AuthGateReason | undefined): AuthSheetReason {
  switch (reason) {
    case 'save':
      return 'save';
    case 'craves':
      return 'craves';
    case 'add-spot':
      return 'add-spot';
    default:
      // The existing AuthSheet's profile copy still references comparative
      // taste language. Until Wave 10 updates that copy, fall back to the
      // neutral default rather than imply public Rank visibility.
      return 'default';
  }
}

export function AuthGateHost() {
  const visible = useAuthGateStore((state) => state.visible);
  const pending = useAuthGateStore((state) => state.pending);
  const toast = useToast((state) => state.show);

  const handleClose = useCallback(async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session?.user) {
      cancelAuthGate();
      return;
    }

    const result = await resumePendingAuthAction();
    if (result.status === 'failed') {
      toast("You're signed in, but CRAVE couldn't finish that action. Try it again.");
    } else if (result.status === 'expired') {
      toast('That action expired. Try it again from where you started.');
    } else if (result.status === 'invalid') {
      toast('That action is no longer available.');
    }
  }, [toast]);

  if (!visible) return null;

  return (
    <Suspense fallback={null}>
      <LazyAuthSheet
        visible
        reason={authSheetReason(pending?.reason)}
        onClose={() => {
          void handleClose();
        }}
      />
    </Suspense>
  );
}
