import {
  cancelAuthGate,
  requestAuthGate,
  resumePendingAuthAction,
  useAuthGateStore,
} from './authGateStore';

describe('authGateStore', () => {
  beforeEach(() => {
    cancelAuthGate();
  });

  it('captures and cancels an anonymous stateful action without executing it', () => {
    const resume = jest.fn();
    requestAuthGate({
      actionType: 'save_place',
      reason: 'save',
      sourceRoute: '/place/1',
      targetIds: ['1'],
      idempotent: true,
      resume,
    });

    expect(useAuthGateStore.getState().visible).toBe(true);
    expect(useAuthGateStore.getState().pending?.actionType).toBe('save_place');

    cancelAuthGate();

    expect(useAuthGateStore.getState().pending).toBeNull();
    expect(resume).not.toHaveBeenCalled();
  });

  it('migrates, revalidates, and resumes exactly once after auth', async () => {
    const migrateAnonymous = jest.fn().mockResolvedValue(undefined);
    const revalidate = jest.fn().mockResolvedValue(true);
    const resume = jest.fn().mockResolvedValue(undefined);

    requestAuthGate({
      actionType: 'rank_place',
      reason: 'rank',
      sourceRoute: '/place/1',
      targetIds: ['1'],
      idempotent: true,
      migrateAnonymous,
      revalidate,
      resume,
    });

    await expect(resumePendingAuthAction()).resolves.toEqual({ status: 'success' });
    await expect(resumePendingAuthAction()).resolves.toEqual({ status: 'expired' });

    expect(migrateAnonymous).toHaveBeenCalledTimes(1);
    expect(revalidate).toHaveBeenCalledTimes(1);
    expect(resume).toHaveBeenCalledTimes(1);
    expect(useAuthGateStore.getState().pending).toBeNull();
  });

  it('does not execute an action that is no longer valid', async () => {
    const resume = jest.fn();
    const onInvalid = jest.fn();

    requestAuthGate({
      actionType: 'follow_user',
      reason: 'follow',
      sourceRoute: '/user/2',
      targetIds: ['2'],
      idempotent: true,
      revalidate: () => false,
      onInvalid,
      resume,
    });

    await expect(resumePendingAuthAction()).resolves.toEqual({ status: 'invalid' });
    expect(onInvalid).toHaveBeenCalledTimes(1);
    expect(resume).not.toHaveBeenCalled();
  });

  it('expires stale intent instead of executing it', async () => {
    const resume = jest.fn();

    requestAuthGate({
      actionType: 'save_place',
      reason: 'save',
      sourceRoute: '/place/1',
      idempotent: true,
      expiresAt: 100,
      resume,
    });

    await expect(resumePendingAuthAction(101)).resolves.toEqual({ status: 'expired' });
    expect(resume).not.toHaveBeenCalled();
  });

  it('retains the envelope when post-auth resume fails', async () => {
    const error = new Error('write failed');

    requestAuthGate({
      actionType: 'save_place',
      reason: 'save',
      sourceRoute: '/place/1',
      idempotent: true,
      resume: () => Promise.reject(error),
    });

    const result = await resumePendingAuthAction();
    expect(result).toEqual({ status: 'failed', error });
    expect(useAuthGateStore.getState().pending?.actionType).toBe('save_place');
    expect(useAuthGateStore.getState().lastError).toBe(error);
  });
});
