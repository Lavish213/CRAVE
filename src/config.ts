export interface BotConfig {
  allowlist: string[];
  maxComments: number;
  maxContextCharacters: number;
  excludedPaths: string[];
  maxOutputTokens: number;
  model: string;
}

const DEFAULTS: BotConfig = {
  allowlist: [],
  maxComments: 20,
  maxContextCharacters: 120_000,
  excludedPaths: ["package-lock.json", "dist/**", "vendor/**"],
  maxOutputTokens: 2_000,
  model: "gpt-5-mini",
};

function boundedInteger(
  value: unknown,
  field: string,
  fallback: number,
  minimum: number,
  maximum: number,
): number {
  if (value === undefined) return fallback;
  if (!Number.isInteger(value) || (value as number) < minimum || (value as number) > maximum) {
    throw new Error(`${field} must be an integer between ${minimum} and ${maximum}`);
  }
  return value as number;
}

function stringArray(value: unknown, field: string, fallback: string[]): string[] {
  if (value === undefined) return fallback;
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !item.trim())) {
    throw new Error(`${field} must be an array of non-empty strings`);
  }
  return value;
}

export function parseConfig(raw: string): BotConfig {
  let input: unknown;
  try {
    input = JSON.parse(raw);
  } catch {
    throw new Error("AI assistant config must be valid JSON");
  }

  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("AI assistant config must be a JSON object");
  }

  const record = input as Record<string, unknown>;
  const authorization = (record.authorization ?? {}) as Record<string, unknown>;
  const context = (record.context ?? {}) as Record<string, unknown>;
  const response = (record.response ?? {}) as Record<string, unknown>;
  const model = record.model ?? DEFAULTS.model;

  if (typeof model !== "string" || !model.trim()) {
    throw new Error("model must be a non-empty string");
  }

  return {
    allowlist: stringArray(authorization.allowlist, "authorization.allowlist", DEFAULTS.allowlist),
    maxComments: boundedInteger(context.max_comments, "context.max_comments", DEFAULTS.maxComments, 1, 50),
    maxContextCharacters: boundedInteger(
      context.max_diff_characters,
      "context.max_diff_characters",
      DEFAULTS.maxContextCharacters,
      1_000,
      200_000,
    ),
    excludedPaths: stringArray(context.excluded_paths, "context.excluded_paths", DEFAULTS.excludedPaths),
    maxOutputTokens: boundedInteger(
      response.max_output_tokens,
      "response.max_output_tokens",
      DEFAULTS.maxOutputTokens,
      100,
      4_000,
    ),
    model,
  };
}
