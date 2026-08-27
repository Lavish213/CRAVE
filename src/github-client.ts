import type { GitHubPort, PullFile } from './orchestrator.js';

interface GitHubClientOptions {
  owner: string;
  repo: string;
  token: string;
  fetcher?: typeof fetch;
}

interface CommentPayload { body?: string | null }

export class GitHubClient implements GitHubPort {
  private readonly baseUrl: string;
  private readonly token: string;
  private readonly fetcher: typeof fetch;

  constructor(options: GitHubClientOptions) {
    this.baseUrl = `https://api.github.com/repos/${encodeURIComponent(options.owner)}/${encodeURIComponent(options.repo)}`;
    this.token = options.token;
    this.fetcher = options.fetcher ?? fetch;
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        accept: 'application/vnd.github+json',
        authorization: `Bearer ${this.token}`,
        'x-github-api-version': '2022-11-28',
        ...(init.body ? { 'content-type': 'application/json' } : {}),
        ...init.headers,
      },
      signal: AbortSignal.timeout(20_000),
    });
    if (!response.ok) throw new Error(`GitHub request failed with status ${response.status}.`);
    return response.json() as Promise<T>;
  }

  async listComments(issueNumber: number): Promise<string[]> {
    const comments = await this.request<CommentPayload[]>(`/issues/${issueNumber}/comments?per_page=100`);
    return comments.map((comment) => comment.body ?? '');
  }

  async listPullFiles(issueNumber: number): Promise<PullFile[]> {
    const files: PullFile[] = [];
    for (let page = 1; page <= 3; page += 1) {
      const batch = await this.request<PullFile[]>(`/pulls/${issueNumber}/files?per_page=100&page=${page}`);
      files.push(...batch);
      if (batch.length < 100) break;
    }
    return files;
  }

  async postComment(issueNumber: number, body: string): Promise<void> {
    await this.request(`/issues/${issueNumber}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    });
  }
}
