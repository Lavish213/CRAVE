import assert from 'node:assert/strict';
import test from 'node:test';

import { GitHubClient } from '../src/github-client.js';

test('reads comments and pull files and posts through repository-scoped endpoints', async () => {
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  const fetcher: typeof fetch = async (input, init) => {
    const url = String(input);
    requests.push({ url, init });
    if (url.includes('/comments') && init?.method === 'POST') return Response.json({}, { status: 201 });
    if (url.includes('/comments')) return Response.json([{ body: 'one' }, { body: null }]);
    if (url.includes('/files')) return Response.json([{ filename: 'src/a.ts', patch: '+line' }]);
    return new Response('missing', { status: 404 });
  };
  const client = new GitHubClient({ owner: 'Lavish213', repo: 'CRAVE', token: 'token', fetcher });

  assert.deepEqual(await client.listComments(4), ['one', '']);
  assert.deepEqual(await client.listPullFiles(4), [{ filename: 'src/a.ts', patch: '+line' }]);
  await client.postComment(4, 'answer');
  assert.ok(requests.every((request) => request.url.startsWith('https://api.github.com/repos/Lavish213/CRAVE/')));
  assert.ok(requests.every((request) => String((request.init?.headers as Record<string, string>).authorization).startsWith('Bearer ')));
});

test('throws sanitized GitHub errors without including response content', async () => {
  const fetcher: typeof fetch = async () => new Response('secret diagnostic', { status: 500 });
  const client = new GitHubClient({ owner: 'o', repo: 'r', token: 'token', fetcher });
  await assert.rejects(() => client.listComments(1), /GitHub request failed with status 500/);
  await assert.rejects(() => client.listComments(1), { message: /^(?!.*secret diagnostic)/ });
});
