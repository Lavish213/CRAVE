import assert from 'node:assert/strict';
import test from 'node:test';

import { parseGitHubEvent } from '../src/github-event.js';

const repository = { name: 'CRAVE', owner: { login: 'Lavish213' } };
const user = { login: 'Lavish213', type: 'User' };

test('normalizes created issue comments and identifies pull requests', () => {
  const parsed = parseGitHubEvent('issue_comment', {
    action: 'created',
    repository,
    issue: { number: 7, title: 'Fix it', body: 'Details', pull_request: { url: 'pr' } },
    comment: { id: 88, body: '/review', author_association: 'OWNER', user },
  });
  assert.deepEqual(parsed, {
    owner: 'Lavish213', repo: 'CRAVE', issueNumber: 7, commentId: 88,
    commentBody: '/review', authorLogin: 'Lavish213', authorAssociation: 'OWNER',
    authorType: 'User', issueTitle: 'Fix it', issueBody: 'Details', isPullRequest: true,
  });
});

test('normalizes created pull request review comments', () => {
  const parsed = parseGitHubEvent('pull_request_review_comment', {
    action: 'created', repository,
    pull_request: { number: 9, title: 'Auth change', body: null },
    comment: { id: 99, body: '/ask Is this safe?', author_association: 'MEMBER', user },
  });
  assert.equal(parsed?.issueNumber, 9);
  assert.equal(parsed?.issueBody, '');
  assert.equal(parsed?.isPullRequest, true);
});

test('ignores edited, deleted, and unsupported events', () => {
  assert.equal(parseGitHubEvent('issue_comment', { action: 'edited' }), null);
  assert.equal(parseGitHubEvent('push', { action: 'created' }), null);
});
