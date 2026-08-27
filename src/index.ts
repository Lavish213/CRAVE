import { readFile } from 'node:fs/promises';

import { parseConfig } from './config.js';
import { GitHubClient } from './github-client.js';
import { parseGitHubEvent } from './github-event.js';
import { OpenAIClient } from './openai-client.js';
import { processEvent } from './orchestrator.js';

async function requiredFile(path: string | undefined, name: string): Promise<string> {
  if (!path) throw new Error(`${name} is not configured.`);
  return readFile(path, 'utf8');
}

async function main(): Promise<void> {
  const eventName = process.env.GITHUB_EVENT_NAME ?? '';
  const eventPayload = JSON.parse(await requiredFile(process.env.GITHUB_EVENT_PATH, 'GITHUB_EVENT_PATH')) as unknown;
  const event = parseGitHubEvent(eventName, eventPayload);
  if (!event) {
    console.log('AI assistant ignored an unsupported event.');
    return;
  }

  const [configRaw, repositoryPolicy] = await Promise.all([
    readFile('.github/ai-assistant.json', 'utf8'),
    readFile('.github/ai-assistant.md', 'utf8'),
  ]);
  const config = parseConfig(configRaw);
  const githubToken = process.env.GITHUB_TOKEN;
  if (!githubToken) throw new Error('GITHUB_TOKEN is not configured.');

  const result = await processEvent(event, {
    github: new GitHubClient({ owner: event.owner, repo: event.repo, token: githubToken }),
    model: new OpenAIClient({
      apiKey: process.env.OPENAI_API_KEY ?? '',
      model: config.model,
      maxOutputTokens: config.maxOutputTokens,
    }),
    repositoryPolicy,
    allowlist: config.allowlist,
    maxComments: config.maxComments,
    maxContextCharacters: config.maxContextCharacters,
    excludedPaths: config.excludedPaths,
  });

  console.log(`AI assistant result: ${result}.`);
}

main().catch(() => {
  console.error('AI assistant failed safely. Check the workflow configuration and service status.');
  process.exitCode = 1;
});
