import assert from 'node:assert/strict';
import test from 'node:test';

import { parseConfig } from '../src/config.js';

test('loads bounded repository configuration with secure defaults', () => {
  const config = parseConfig(JSON.stringify({
    authorization: { allowlist: ['trusted-dev'] },
    context: { max_comments: 10, max_diff_characters: 50_000, excluded_paths: ['vendor/**'] },
    response: { max_output_tokens: 1_000 },
    model: 'gpt-5-mini',
  }));
  assert.deepEqual(config.allowlist, ['trusted-dev']);
  assert.equal(config.maxComments, 10);
  assert.equal(config.maxContextCharacters, 50_000);
  assert.equal(config.maxOutputTokens, 1_000);
});

test('rejects unsafe limits instead of silently enabling uncontrolled spending', () => {
  assert.throws(() => parseConfig('{"response":{"max_output_tokens":999999}}'), /max_output_tokens/);
  assert.throws(() => parseConfig('{"context":{"max_diff_characters":9999999}}'), /max_diff_characters/);
});
