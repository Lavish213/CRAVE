import assert from 'node:assert/strict';
import test from 'node:test';

import { isAuthorized } from '../src/authorize.js';

test('authorizes repository owners, members, and collaborators', () => {
  for (const association of ['OWNER', 'MEMBER', 'COLLABORATOR']) {
    assert.equal(isAuthorized({ login: 'dev', association, actorType: 'User' }), true);
  }
});

test('rejects bots and arbitrary public users by default', () => {
  assert.equal(isAuthorized({ login: 'dependabot[bot]', association: 'CONTRIBUTOR', actorType: 'Bot' }), false);
  assert.equal(isAuthorized({ login: 'stranger', association: 'CONTRIBUTOR', actorType: 'User' }), false);
});

test('supports an explicit allowlist without weakening bot rejection', () => {
  assert.equal(isAuthorized({ login: 'trusted', association: 'NONE', actorType: 'User' }, ['trusted']), true);
  assert.equal(isAuthorized({ login: 'trusted', association: 'NONE', actorType: 'Bot' }, ['trusted']), false);
});
