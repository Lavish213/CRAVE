import { isAuthorized } from './authorize.js';
import { CommandError, parseCommand } from './commands.js';
import { buildPrompt, redactSecrets, type ModelPrompt } from './prompt.js';
import { formatResponse, hasProcessedComment } from './responder.js';

export interface CommentEvent {
  owner: string;
  repo: string;
  issueNumber: number;
  commentId: number;
  commentBody: string;
  authorLogin: string;
  authorAssociation: string;
  authorType: string;
  issueTitle: string;
  issueBody: string;
  isPullRequest: boolean;
}

export interface PullFile {
  filename: string;
  patch?: string | null;
}

export interface GitHubPort {
  listComments(issueNumber: number): Promise<string[]>;
  listPullFiles(issueNumber: number): Promise<PullFile[]>;
  postComment(issueNumber: number, body: string): Promise<void>;
}

export interface ModelPort {
  complete(prompt: ModelPrompt): Promise<string>;
}

export interface BotDependencies {
  github: GitHubPort;
  model: ModelPort;
  repositoryPolicy: string;
  allowlist?: string[];
  maxComments?: number;
  maxContextCharacters?: number;
  excludedPaths?: string[];
}

export type ProcessResult = 'ignored' | 'unauthorized' | 'duplicate' | 'replied' | 'failed';

const HELP = [
  '`/ask <question>` — ask about the issue or pull request.',
  '`/review [instructions]` — review a pull-request diff.',
  '`/summarize` — summarize the conversation or pull request.',
  '`/help` — show this message.',
].join('\n\n');

function isExcluded(filename: string, patterns: readonly string[]): boolean {
  return patterns.some((pattern) => {
    if (pattern.endsWith('/**')) return filename.startsWith(pattern.slice(0, -3));
    return filename === pattern;
  });
}

function buildContext(event: CommentEvent, comments: readonly string[], files: readonly PullFile[], deps: BotDependencies): string {
  const maxComments = deps.maxComments ?? 20;
  const excluded = deps.excludedPaths ?? ['package-lock.json', 'dist/**', 'vendor/**'];
  const sections = [
    `Repository: ${event.owner}/${event.repo}`,
    `Title: ${event.issueTitle}`,
    `Description:\n${event.issueBody || '(none)'}`,
    `Recent comments:\n${comments.slice(-maxComments).join('\n\n---\n\n') || '(none)'}`,
  ];
  if (files.length) {
    const patches = files
      .filter((file) => !isExcluded(file.filename, excluded))
      .map((file) => `File: ${file.filename}\n${file.patch ?? '[Patch unavailable]'}`)
      .join('\n\n---\n\n');
    sections.push(`Pull request changes:\n${patches || '(all changed paths excluded)'}`);
  }
  return sections.join('\n\n');
}

export async function processEvent(event: CommentEvent, deps: BotDependencies): Promise<ProcessResult> {
  if (event.authorType === 'Bot' || event.authorLogin.endsWith('[bot]')) return 'ignored';

  let command;
  try {
    command = parseCommand(event.commentBody);
  } catch (error) {
    if (!(error instanceof CommandError)) throw error;
    await deps.github.postComment(event.issueNumber, formatResponse(error.message, event.commentId, 'help'));
    return 'replied';
  }
  if (!command) return 'ignored';

  if (!isAuthorized({
    login: event.authorLogin,
    association: event.authorAssociation,
    actorType: event.authorType,
  }, deps.allowlist)) {
    await deps.github.postComment(
      event.issueNumber,
      formatResponse('Only authorized collaborators may invoke the AI assistant.', event.commentId, 'help'),
    );
    return 'unauthorized';
  }

  const comments = await deps.github.listComments(event.issueNumber);
  if (hasProcessedComment(comments, event.commentId)) return 'duplicate';

  if (command.name === 'help') {
    await deps.github.postComment(event.issueNumber, formatResponse(HELP, event.commentId, 'help'));
    return 'replied';
  }
  if (command.name === 'review' && !event.isPullRequest) {
    await deps.github.postComment(
      event.issueNumber,
      formatResponse('`/review` is available only on pull requests.', event.commentId, 'review'),
    );
    return 'replied';
  }

  const files = event.isPullRequest && (command.name === 'review' || command.name === 'ask' || command.name === 'summarize')
    ? await deps.github.listPullFiles(event.issueNumber)
    : [];
  const context = buildContext(event, comments, files, deps);
  const prompt = buildPrompt({
    command: command.name,
    instructions: command.instructions,
    repositoryPolicy: deps.repositoryPolicy,
    context,
    maxContextCharacters: deps.maxContextCharacters,
  });

  try {
    const answer = redactSecrets(await deps.model.complete(prompt));
    await deps.github.postComment(event.issueNumber, formatResponse(answer, event.commentId, command.name));
    return 'replied';
  } catch {
    await deps.github.postComment(
      event.issueNumber,
      formatResponse('The AI service is temporarily unavailable. Please try again later.', event.commentId, command.name),
    );
    return 'failed';
  }
}
