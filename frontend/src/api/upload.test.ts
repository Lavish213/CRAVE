// See videos.test.ts for why this needs its own fake XHR class rather
// than an ambient one: XMLHttpRequest isn't defined in this jest
// environment at all.
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

// See videos.test.ts for why this extra flush is needed: the real code's
// fetch(fileUri).then(blob).then(xhr-setup) chain needs several
// microtask ticks before the XHR instance actually exists.
async function flushMicrotasks(times = 10) {
  for (let i = 0; i < times; i++) {
    await Promise.resolve();
  }
}

describe('uploadToSignedUrl', () => {
  const fakeBlob = { size: 42 };

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

  it('PUTs the file to the signed URL and reports progress as a 0-1 fraction', async () => {
    const { uploadToSignedUrl } = require('./upload');
    const onProgress = jest.fn();

    const promise = uploadToSignedUrl('https://r2.example/put-url', 'file:///photo.jpg', 'image/jpeg', onProgress);
    await flushMicrotasks();

    const xhr = FakeXHR.instances[0];
    expect(xhr.method).toBe('PUT');
    expect(xhr.requestHeaders['Content-Type']).toBe('image/jpeg');
    expect(xhr.sentBody).toBe(fakeBlob);

    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 2 });
    expect(onProgress).toHaveBeenCalledWith(0.5);

    xhr.status = 204;
    xhr.onload?.();
    await expect(promise).resolves.toBeUndefined();
  });

  it('rejects when the server responds with a non-2xx status', async () => {
    const { uploadToSignedUrl } = require('./upload');
    const promise = uploadToSignedUrl('https://r2.example/put-url', 'file:///photo.jpg', 'image/jpeg');
    await flushMicrotasks();

    const xhr = FakeXHR.instances[0];
    xhr.status = 403;
    xhr.onload?.();

    await expect(promise).rejects.toThrow('Upload to storage failed (status 403)');
  });

  it('still resolves with no onProgress callback passed at all', async () => {
    const { uploadToSignedUrl } = require('./upload');
    const promise = uploadToSignedUrl('https://r2.example/put-url', 'file:///photo.jpg', 'image/jpeg');
    await flushMicrotasks();

    const xhr = FakeXHR.instances[0];
    xhr.status = 200;
    xhr.onload?.();

    await expect(promise).resolves.toBeUndefined();
  });
});
