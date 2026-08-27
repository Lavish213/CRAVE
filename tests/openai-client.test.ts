import assert from 'node:assert/strict';
import test from 'node:test';

import { OpenAIClient } from '../src/openai-client.js';

test('retries one transient server failure and returns bounded output', async () => {
  let requests = 0;
  const fetcher: typeof fetch = async () => {
    requests += 1;
    if (requests === 1) return new Response('temporary', { status: 503 });
    return Response.json({ output_text: 'resolved' });
  };
  const client = new OpenAIClient({ apiKey: 'test', fetcher, sleep: async () => {} });

  assert.equal(await client.complete({ system: 'policy', user: 'context' }), 'resolved');
  assert.equal(requests, 2);
});

test('does not retry rate limits and never includes response bodies in errors', async () => {
  let requests = 0;
  const fetcher: typeof fetch = async () => {
    requests += 1;
    return new Response('secret upstream detail', { status: 429 });
  };
  const client = new OpenAIClient({ apiKey: 'test', fetcher, sleep: async () => {} });

  await assert.rejects(() => client.complete({ system: 'policy', user: 'context' }), /status 429/);
  await assert.rejects(() => client.complete({ system: 'policy', user: 'context' }), { message: /^(?!.*secret upstream detail)/ });
  assert.equal(requests, 2);
});
