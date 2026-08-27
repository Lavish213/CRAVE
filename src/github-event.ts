import type { CommentEvent } from './orchestrator.js';

type UnknownRecord = Record<string, unknown>;

function record(value: unknown): UnknownRecord {
  return value && typeof value === 'object' ? value as UnknownRecord : {};
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function number(value: unknown): number {
  return typeof value === 'number' ? value : Number.NaN;
}

export function parseGitHubEvent(eventName: string, rawPayload: unknown): CommentEvent | null {
  const payload = record(rawPayload);
  if (payload.action !== 'created') return null;
  if (eventName !== 'issue_comment' && eventName !== 'pull_request_review_comment') return null;

  const repository = record(payload.repository);
  const owner = record(repository.owner);
  const comment = record(payload.comment);
  const user = record(comment.user);
  const subject = eventName === 'issue_comment' ? record(payload.issue) : record(payload.pull_request);
  const issueNumber = number(subject.number);
  const commentId = number(comment.id);
  if (!text(owner.login) || !text(repository.name) || !Number.isFinite(issueNumber) || !Number.isFinite(commentId)) {
    throw new Error('GitHub event is missing required repository, issue, or comment fields.');
  }

  return {
    owner: text(owner.login),
    repo: text(repository.name),
    issueNumber,
    commentId,
    commentBody: text(comment.body),
    authorLogin: text(user.login),
    authorAssociation: text(comment.author_association),
    authorType: text(user.type),
    issueTitle: text(subject.title),
    issueBody: text(subject.body),
    isPullRequest: eventName === 'pull_request_review_comment' || Boolean(subject.pull_request),
  };
}
