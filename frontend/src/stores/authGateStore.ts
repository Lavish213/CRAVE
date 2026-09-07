import { create } from 'zustand';

export type AuthGateReason =
  | 'save'
  | 'craves'
  | 'rank'
  | 'post-log'
  | 'follow'
  | 'profile-identity'
  | 'add-spot'
  | 'account-privacy'
  | 'default';

export interface AuthResumeEnvelope {
  actionType: string;
  reason: AuthGateReason;
  sourceRoute: string;
  targetIds?: readonly string[];
  payload?: Readonly<Record<string, unknown>>;
  destination?: string;
  idempotent: boolean;
  expiresAt: number;
  migrateAnonymous?: () => Promise<void> | void;
  revalidate?: () => Promise<boolean> | boolean;
  onInvalid?: () => Promise<void> | void;
  resume: () => Promise<void> | void;
}

export type AuthResumeResult =
  | { status: 'success' }
  | { status: 'invalid' }
  | { status: 'expired' }
  | { status: 'in_progress' }
  | { status: 'failed'; error: unknown };

interface AuthGateState {
  visible: boolean;
  processing: boolean;
  pending: AuthResumeEnvelope | null;
  lastError: unknown | null;
}

const INITIAL_STATE: AuthGateState = {
  visible: false,
  processing: false,
  pending: null,
  lastError: null,
};

export const useAuthGateStore = create<AuthGateState>(() => INITIAL_STATE);

export interface RequestAuthGateInput extends Omit<AuthResumeEnvelope, 'expiresAt'> {
  expiresAt?: number;
  ttlMs?: number;
}

const DEFAULT_TTL_MS = 5 * 60 * 1000;

export function requestAuthGate(input: RequestAuthGateInput): void {
  const expiresAt = input.expiresAt ?? Date.now() + (input.ttlMs ?? DEFAULT_TTL_MS);
  const { ttlMs: _ttlMs, ...envelope } = input;
  useAuthGateStore.setState({
    visible: true,
    processing: false,
    pending: { ...envelope, expiresAt },
    lastError: null,
  });
}

export function cancelAuthGate(): void {
  useAuthGateStore.setState(INITIAL_STATE);
}

export function clearAuthGate(): void {
  cancelAuthGate();
}

export async function resumePendingAuthAction(now = Date.now()): Promise<AuthResumeResult> {
  const state = useAuthGateStore.getState();
  if (state.processing) return { status: 'in_progress' };

  const envelope = state.pending;
  if (!envelope || envelope.expiresAt <= now) {
    useAuthGateStore.setState(INITIAL_STATE);
    return { status: 'expired' };
  }

  useAuthGateStore.setState({ visible: false, processing: true, lastError: null });

  try {
    await envelope.migrateAnonymous?.();
    const valid = envelope.revalidate ? await envelope.revalidate() : true;
    if (!valid) {
      await envelope.onInvalid?.();
      useAuthGateStore.setState(INITIAL_STATE);
      return { status: 'invalid' };
    }

    await envelope.resume();
    useAuthGateStore.setState(INITIAL_STATE);
    return { status: 'success' };
  } catch (error) {
    useAuthGateStore.setState({
      visible: false,
      processing: false,
      pending: envelope,
      lastError: error,
    });
    return { status: 'failed', error };
  }
}
