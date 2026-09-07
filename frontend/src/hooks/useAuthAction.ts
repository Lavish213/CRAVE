import { useCallback } from 'react';
import { useAuthStore } from '../stores/authStore';
import {
  requestAuthGate,
  type RequestAuthGateInput,
} from '../stores/authGateStore';

export type AuthActionResult = 'executed' | 'gated' | 'invalid';

/**
 * Single entry point for account-owned actions.
 *
 * Authenticated users execute immediately after revalidation. Anonymous users
 * get the same action captured in the shared resume envelope and AuthSheet is
 * opened by the root AuthGateHost. Screens should not add their own
 * `if (!user) ...` branches for new stateful actions.
 */
export function useAuthAction() {
  const user = useAuthStore((state) => state.user);

  return useCallback(async (input: RequestAuthGateInput): Promise<AuthActionResult> => {
    if (!user) {
      requestAuthGate(input);
      return 'gated';
    }

    const valid = input.revalidate ? await input.revalidate() : true;
    if (!valid) {
      await input.onInvalid?.();
      return 'invalid';
    }

    await input.resume();
    return 'executed';
  }, [user]);
}
