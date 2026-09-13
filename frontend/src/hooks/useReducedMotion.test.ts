import { act, renderHook, waitFor } from '@testing-library/react-native';
import { AccessibilityInfo } from 'react-native';
import { useReducedMotion } from './useReducedMotion';

describe('useReducedMotion', () => {
  it('reflects the current OS Reduce Motion setting once resolved', async () => {
    jest.spyOn(AccessibilityInfo, 'isReduceMotionEnabled').mockResolvedValue(true);
    const addEventListenerSpy = jest.spyOn(AccessibilityInfo, 'addEventListener');

    const { result } = renderHook(() => useReducedMotion());

    expect(result.current).toBe(false);
    await waitFor(() => expect(result.current).toBe(true));

    expect(addEventListenerSpy).toHaveBeenCalledWith('reduceMotionChanged', expect.any(Function));
  });

  it('updates when the OS setting changes while mounted', async () => {
    jest.spyOn(AccessibilityInfo, 'isReduceMotionEnabled').mockResolvedValue(false);
    let changeHandler: ((value: boolean) => void) | undefined;
    jest.spyOn(AccessibilityInfo, 'addEventListener').mockImplementation(((
      _event: string,
      handler: (value: boolean) => void,
    ) => {
      changeHandler = handler;
      return { remove: jest.fn() };
    }) as unknown as typeof AccessibilityInfo.addEventListener);

    const { result } = renderHook(() => useReducedMotion());
    await waitFor(() => expect(result.current).toBe(false));

    act(() => {
      changeHandler?.(true);
    });

    expect(result.current).toBe(true);
  });

  it('unsubscribes on unmount', async () => {
    jest.spyOn(AccessibilityInfo, 'isReduceMotionEnabled').mockResolvedValue(false);
    const remove = jest.fn();
    jest.spyOn(AccessibilityInfo, 'addEventListener').mockReturnValue({
      remove,
    } as unknown as ReturnType<typeof AccessibilityInfo.addEventListener>);

    const { unmount } = renderHook(() => useReducedMotion());
    await waitFor(() => expect(remove).not.toHaveBeenCalled());

    unmount();

    expect(remove).toHaveBeenCalled();
  });
});
