import assert from 'node:assert/strict';
import test from 'node:test';

import { CommandError, parseCommand } from '../src/commands.js';

test('parses a supported command only at the beginning of a comment', () => {
  assert.deepEqual(parseCommand('/ask Why is this failing?'), {
    name: 'ask',
    instructions: 'Why is this failing?',
  });
  assert.equal(parseCommand('please /ask why'), null);
  assert.equal(parseCommand('/asking why'), null);
});

test('allows optional review instructions and argument-free commands', () => {
  assert.deepEqual(parseCommand('/review focus on auth'), {
    name: 'review',
    instructions: 'focus on auth',
  });
  assert.deepEqual(parseCommand('/summarize'), { name: 'summarize', instructions: '' });
  assert.deepEqual(parseCommand('/help'), { name: 'help', instructions: '' });
});

test('rejects missing ask text and oversized instructions', () => {
  assert.throws(() => parseCommand('/ask'), CommandError);
  assert.throws(() => parseCommand(`/ask ${'x'.repeat(4001)}`), /4,000/);
});
