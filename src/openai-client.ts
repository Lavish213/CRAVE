import type { ModelPrompt } from './prompt.js';

interface OpenAIClientOptions {
  apiKey: string;
  model?: string;
  maxOutputTokens?: number;
  fetcher?: typeof fetch;
  sleep?: (milliseconds: number) => Promise<void>;
}

interface ResponsesPayload {
  output_text?: string;
  output?: Array<{ content?: Array<{ type?: string; text?: string }> }>;
}

export class OpenAIClient {
  private readonly apiKey: string;
  private readonly model: string;
  private readonly maxOutputTokens: number;
  private readonly fetcher: typeof fetch;
  private readonly sleep: (milliseconds: number) => Promise<void>;

  constructor(options: OpenAIClientOptions) {
    this.apiKey = options.apiKey;
    this.model = options.model ?? 'gpt-5-mini';
    this.maxOutputTokens = options.maxOutputTokens ?? 2_000;
    this.fetcher = options.fetcher ?? fetch;
    this.sleep = options.sleep ?? ((milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)));
  }

  async complete(prompt: ModelPrompt): Promise<string> {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      let response: Response;
      try {
        response = await this.fetcher('https://api.openai.com/v1/responses', {
          method: 'POST',
          headers: {
            authorization: `Bearer ${this.apiKey}`,
            'content-type': 'application/json',
          },
          body: JSON.stringify({
            model: this.model,
            instructions: prompt.system,
            input: prompt.user,
            max_output_tokens: this.maxOutputTokens,
            store: false,
          }),
          signal: AbortSignal.timeout(30_000),
        });
      } catch (error) {
        if (attempt === 0) {
          await this.sleep(500);
          continue;
        }
        throw new Error('OpenAI request failed before receiving a response.', { cause: error });
      }

      if (response.ok) {
        const payload = await response.json() as ResponsesPayload;
        const text = payload.output_text ?? payload.output
          ?.flatMap((item) => item.content ?? [])
          .filter((content) => content.type === 'output_text')
          .map((content) => content.text ?? '')
          .join('\n');
        if (!text?.trim()) throw new Error('OpenAI returned no usable text.');
        return text.trim();
      }

      const isTransient = response.status >= 500 && response.status <= 599;
      if (isTransient && attempt === 0) {
        await this.sleep(500);
        continue;
      }
      throw new Error(`OpenAI request failed with status ${response.status}.`);
    }
    throw new Error('OpenAI request failed.');
  }
}
