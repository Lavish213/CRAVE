import { useToast } from '../../hooks/useToast';

/**
 * UI V2 toast facade. The existing ToastContainer remains the single mounted
 * host in the root layout; this file intentionally does not create another
 * provider/container.
 */
export const useCraveToast = useToast;

export function showCraveToast(message: string, durationMs?: number) {
  useToast.getState().show(message, durationMs);
}

export function hideCraveToast() {
  useToast.getState().hide();
}
