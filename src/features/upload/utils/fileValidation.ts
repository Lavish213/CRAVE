const MAX_MB = 15;

export function validateImage(fileSizeBytes: number): true {
  if (!Number.isFinite(fileSizeBytes) || fileSizeBytes <= 0) {
    throw new Error('Invalid file size');
  }

  const sizeMb = fileSizeBytes / (1024 * 1024);

  if (sizeMb > MAX_MB) {
    throw new Error('Image too large (max 15MB)');
  }

  return true;
}
