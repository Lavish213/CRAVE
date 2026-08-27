import assert from 'node:assert/strict';
import test from 'node:test';

import { formatResponse, hasProcessedComment, responseMarker } from '../src/responder.js';

test('uses a stable hidden source-comment marker for deduplication', () => {
  const marker = responseMarker(12345);
  assert.equal(marker, '<!-- crave-ai-source-comment:12345 -->');
  assert.equal(hasProcessedComment(['hello', `answer\n${marker}`], 12345), true);
  assert.equal(hasProcessedComment(['hello'], 12345), false);
});

test('labels every response as AI-generated and includes the marker', () => {
  const response = formatResponse('Direct answer', 99, 'ask');
  assert.match(response, /^### AI answer/);
  assert.match(response, /Verify important findings/);
  assert.match(response, /crave-ai-source-comment:99/);
});
