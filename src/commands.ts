export type CommandName = 'ask' | 'review' | 'summarize' | 'help';

export interface ParsedCommand {
  name: CommandName;
  instructions: string;
}

export class CommandError extends Error {}

const MAX_INSTRUCTION_CHARACTERS = 4_000;
const COMMAND_PATTERN = /^\/(ask|review|summarize|help)(?:\s+([\s\S]*))?\s*$/;

export function parseCommand(body: string): ParsedCommand | null {
  const match = COMMAND_PATTERN.exec(body.trim());
  if (!match) return null;

  const name = match[1] as CommandName;
  const instructions = (match[2] ?? '').trim();
  if (name === 'ask' && !instructions) {
    throw new CommandError('/ask requires a question. Try `/ask Why is this test failing?`');
  }
  if ((name === 'help' || name === 'summarize') && instructions) {
    throw new CommandError(`/${name} does not accept additional text.`);
  }
  if (instructions.length > MAX_INSTRUCTION_CHARACTERS) {
    throw new CommandError('Command instructions must be 4,000 characters or fewer.');
  }
  return { name, instructions };
}
