// src/lib/queryClient.ts
//
// Single shared React Query client, lifted out of app/_layout.tsx so
// non-component code (authStore's signOut) can import and clear it
// without a circular import through the root layout screen.
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,     // 2 min default
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
