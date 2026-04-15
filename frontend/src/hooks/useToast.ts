// src/hooks/useToast.ts
import { create } from 'zustand';

interface ToastState {
  message: string | null;
  show: (msg: string, durationMs?: number) => void;
  hide: () => void;
}

let _timer: ReturnType<typeof setTimeout> | null = null;

export const useToast = create<ToastState>((set) => ({
  message: null,
  show: (msg, durationMs = 2800) => {
    if (_timer) clearTimeout(_timer);
    set({ message: msg });
    _timer = setTimeout(() => set({ message: null }), durationMs);
  },
  hide: () => {
    if (_timer) clearTimeout(_timer);
    set({ message: null });
  },
}));
