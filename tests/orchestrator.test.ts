import assert from 'node:assert/strict';
import test from 'node:test';

import { processEvent, type BotDependencies, type CommentEvent } from '../src/orchestrator.js';

function event(overrides: Partial<CommentEvent> = {}): CommentEvent {
  return {
    owner: 'Lavish213',
    repo: 'CRAVE',
    issueNumber: 42,
    commentId: 700,
    commentBody: '/ask Why is this failing?',
    authorLogin: 'Lavish213',
    authorAssociation: 'OWNER',
    authorType: 'User',
    issueTitle: 'Broken test',
    issueBody: 'The test fails on CI.',
    isPullRequest: false,
    ...overrides,
  };
}

function dependencies() {
  const calls = { model: 0, posts: [] as string[] };
  const deps: BotDependencies = {
    github: {
      listComments: async () => [],
      listPullFiles: async () => [],
      postComment: async (_issueNumber, body) => { calls.posts.push(body); },
    },
    model: {
      complete: async () => {
        calls.model += 1;
        return 'The failure is caused by a stale fixture.';
      },
    },
    repositoryPolicy: 'Never execute code.',
  };
  return { calls, deps };
}

test('ignores bot comments and unsupported natural language without spending model tokens', async () => {
  for (const candidate of [
    event({ authorType: 'Bot', authorLogin: 'helper[bot]' }),
    event({ commentBody: 'Could somebody review this?' }),
  ]) {
    const { calls, deps } = dependencies();
    assert.equal(await processEvent(candidate, deps), 'ignored');
    assert.equal(calls.model, 0);
    assert.deepEqual(calls.posts, []);
  }
});

test('denies unauthorized users before context collection or model calls', async () => {
  const { calls, deps } = dependencies();
  assert.equal(await processEvent(event({ authorAssociation: 'CONTRIBUTOR' }), deps), 'unauthorized');
  assert.equal(calls.model, 0);
  assert.match(calls.posts[0] ?? '', /authorized collaborators/i);
});

test('deduplicates repeated webhook deliveries using the source comment marker', async () => {
  const { calls, deps } = dependencies();
  deps.github.listComments = async () => ['answer\n<!-- crave-ai-source-comment:700 -->'];
  assert.equal(await processEvent(event(), deps), 'duplicate');
  assert.equal(calls.model, 0);
  assert.deepEqual(calls.posts, []);
});

test('answers help locally without making a paid model request', async () => {
  const { calls, deps } = dependencies();
  assert.equal(await processEvent(event({ commentBody: '/help' }), deps), 'replied');
  assert.equal(calls.model, 0);
  assert.match(calls.posts[0] ?? '', /\/ask/);
  assert.match(calls.posts[0] ?? '', /\/review/);
});

test('sends bounded issue context to the model and posts one marked answer', async () => {
  const { calls, deps } = dependencies();
  deps.github.listComments = async () => ['first comment', 'second comment'];
  let modelUserPrompt = '';
  deps.model.complete = async (prompt) => {
    calls.model += 1;
    modelUserPrompt = prompt.user;
    return 'Check the fixture path.';
  };

  assert.equal(await processEvent(event(), deps), 'replied');
  assert.equal(calls.model, 1);
  assert.match(modelUserPrompt, /Broken test/);
  assert.match(modelUserPrompt, /second comment/);
  assert.equal(calls.posts.length, 1);
  assert.match(calls.posts[0] ?? '', /crave-ai-source-comment:700/);
});

test('review includes patches but excludes dependency and generated paths', async () => {
  const { deps } = dependencies();
  deps.github.listPullFiles = async () => [
    { filename: 'src/auth.ts', patch: '@@ -1 +1 @@\n-old\n+new' },
    { filename: 'package-lock.json', patch: 'huge lock diff' },
    { filename: 'dist/app.js', patch: 'generated bundle' },
  ];
  let modelUserPrompt = '';
  deps.model.complete = async (prompt) => {
    modelUserPrompt = prompt.user;
    return 'No high-severity findings.';
  };

  await processEvent(event({ commentBody: '/review focus on auth', isPullRequest: true }), deps);
  assert.match(modelUserPrompt, /src\/auth\.ts/);
  assert.doesNotMatch(modelUserPrompt, /package-lock/);
  assert.doesNotMatch(modelUserPrompt, /dist\/app/);
});

test('reports model failures without exposing internal error details', async () => {
  const { calls, deps } = dependencies();
  deps.model.complete = async () => { throw new Error('OPENAI_API_KEY=super-secret'); };

  assert.equal(await processEvent(event(), deps), 'failed');
  assert.equal(calls.posts.length, 1);
  assert.match(calls.posts[0] ?? '', /temporarily unavailable/i);
  assert.doesNotMatch(calls.posts[0] ?? '', /super-secret|OPENAI_API_KEY/);
});
