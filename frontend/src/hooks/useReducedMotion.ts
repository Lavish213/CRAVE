/**
 * useReducedMotion.ts
 *
 * Wraps AccessibilityInfo's Reduce Motion setting (iOS Settings >
 * Accessibility > Motion > Reduce Motion; Android Settings > Accessibility
 * > Remove animations). The accessibility certification runbook
 * (docs/RUNBOOK_ACCESSIBILITY_CERTIFICATION.md) flagged this as never
 * checked anywhere in the app -- every animated transition (SkeletonCard's
 * shimmer loop, MapBottomSheet's bouncy release spring, PlaceCard's save
 * scale-pop) always ran at full motion regardless of the user's own OS
 * preference.
 *
 * Plain opacity fades (Toast, Feed's initial fade-in) are deliberately left
 * alone at call sites even after this hook exists -- Reduce Motion targets
 * parallax/bounce/zoom-style motion, not a simple one-shot fade.
 */
import { useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    let mounted = true;
    AccessibilityInfo.isReduceMotionEnabled().then((value) => {
      if (mounted) setReduced(value);
    });
    const subscription = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      setReduced,
    );
    return () => {
      mounted = false;
      subscription.remove();
    };
  }, []);

  return reduced;
}
