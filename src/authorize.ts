export interface CommentAuthor {
  login: string;
  association: string;
  actorType: string;
}

const TRUSTED_ASSOCIATIONS = new Set(['OWNER', 'MEMBER', 'COLLABORATOR']);

export function isAuthorized(author: CommentAuthor, allowlist: readonly string[] = []): boolean {
  if (author.actorType === 'Bot' || author.login.endsWith('[bot]')) return false;
  return TRUSTED_ASSOCIATIONS.has(author.association) || allowlist.includes(author.login);
}
