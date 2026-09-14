// XMLHttpRequest isn't defined in this jest environment (jest-expo's
// preset doesn't polyfill it -- confirmed by checking `typeof
// (global as any).XMLHttpRequest` under this exact config, which comes
// back undefined), so uploadVideoToSignedUrl's XHR usage needs its own
// fake class here rather than relying on any ambient mock.
class FakeXHR {
  static instances: FakeXHR[] = [];

  method: string | null = null;
  url: string | null = null;
  requestHeaders: Record<string, string> = {};
  sentBody: unknown = null;
  status = 0;

  upload: { onprogress: ((event: any) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;

  constructor() {
    FakeXHR.instances.push(this);
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.requestHeaders[name] = value;
  }

  send(body: unknown) {
    this.sentBody = body;
  }
}

// The real code chains fetch(fileUri).then(blob).then(xhr-setup) -- each
// .then whose callback itself returns a promise (blob(), and the mocked
// fetch's own Promise.resolve wrapper) costs an extra microtask tick to
// unwrap, so a single `await Promise.resolve()` isn't enough to reach the
// point where the XHR instance has actually been constructed.
async function flushMicrotasks(times = 10) {
  for (let i = 0; i < times; i++) {
    await Promise.resolve();
  }
}

describe('uploadVideoToSignedUrl', () => {
  const fakeBlob = { size: 1234 };

  beforeEach(() => {
    FakeXHR.instances = [];
    (global as any).XMLHttpRequest = FakeXHR;
    (global as any).fetch = jest.fn(() =>
      Promise.resolve({ blob: () => Promise.resolve(fakeBlob) })
    );
  });

  afterEach(() => {
    delete (global as any).XMLHttpRequest;
    delete (global as any).fetch;
  });

  it('reports upload progress as a 0-1 fraction, not a 0-100 percentage', async () => {
    const { uploadVideoToSignedUrl } = require('./videos');
    const onProgress = jest.fn();

    const promise = uploadVideoToSignedUrl(
      'https://r2.example/put-url',
      'file:///clip.mp4',
      'video/mp4',
      onProgress
    );
    await flushMicrotasks();

    const xhr = FakeXHR.instances[0];
    expect(xhr.method).toBe('PUT');
    expect(xhr.url).toBe('https://r2.example/put-url');
    expect(xhr.requestHeaders['Content-Type']).toBe('video/mp4');
    expect(xhr.sentBody).toBe(fakeBlob);

    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 25, total: 100 });
    expect(onProgress).toHaveBeenCalledWith(0.25);

    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 100, total: 100 });
    expect(onProgress).toHaveBeenCalledWith(1);

    xhr.status = 200;
    xhr.onload?.();
    await expect(promise).resolves.toBeUndefined();
  });

  it('ignores a non-length-computable progress event instead of reporting a bogus fraction', async () => {
    const { uploadVideoToSignedUrl } = require('./videos');
    const onProgress = jest.fn();

    const promise = uploadVideoToSignedUrl('https://r2.example/put-url', 'file:///clip.mp4', 'video/mp4', onProgress);
    await flushMicrotasks();

    const xhr = FakeXHR.instances[0];
    xhr.upload.onprogress?.({ lengthComputable: false, loaded: 10, total: 0 });
    expect(onProgress).not.toHaveBeenCalled();

    xhr.status = 200;
    xhr.onload?.();
    await promise;
  });

  it('rejects when the server responds with a non-2xx status', async () => {
    const { uploadVideoToSignedUrl } = require('./videos');
    const promise = uploadVideoToSignedUrl('https://r2.example/put-url', 'file:///clip.mp4', 'video/mp4');
    await flushMicrotasks();

    const xhr = FakeXHR.instances[0];
    xhr.status = 500;
    xhr.onload?.();

    await expect(promise).rejects.toThrow('Upload to storage failed (status 500)');
  });

  it('rejects on a network error without ever calling onProgress', async () => {
    const { uploadVideoToSignedUrl } = require('./videos');
    const onProgress = jest.fn();
    const promise = uploadVideoToSignedUrl('https://r2.example/put-url', 'file:///clip.mp4', 'video/mp4', onProgress);
    await flushMicrotasks();

    const xhr = FakeXHR.instances[0];
    xhr.onerror?.();

    await expect(promise).rejects.toThrow('Upload to storage failed (network error)');
    expect(onProgress).not.toHaveBeenCalled();
  });

  it('works with no onProgress callback at all (optional parameter)', async () => {
    const { uploadVideoToSignedUrl } = require('./videos');
    const promise = uploadVideoToSignedUrl('https://r2.example/put-url', 'file:///clip.mp4', 'video/mp4');
    await flushMicrotasks();

    const xhr = FakeXHR.instances[0];
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 10 });
    xhr.status = 200;
    xhr.onload?.();

    await expect(promise).resolves.toBeUndefined();
  });
});
