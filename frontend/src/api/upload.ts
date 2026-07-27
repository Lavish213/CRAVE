// Place photo upload — request a signed R2 URL, PUT the file directly to
// storage, then confirm so the backend queues processing.
//
// This mirrors the flow that used to live at the repo-root `src/features/
// upload/` tree, which was never part of this Expo app (it sat outside
// `frontend/`, imported a `@/data/client/apiClient` module that doesn't
// exist anywhere in the repo, and its backend calls used a request shape
// FastAPI would have rejected). Rebuilt here against the real `client` and
// the real backend contract (JSON body, not query params — see
// backend/app/api/v1/endpoints/upload.py).
import { client } from './client';

export const ALLOWED_UPLOAD_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const;
export type UploadContentType = (typeof ALLOWED_UPLOAD_TYPES)[number];

export const MAX_UPLOAD_MB = 15;

export type UploadStatus = 'pending' | 'processing' | 'ready' | 'failed';

export interface UploadRequestPayload {
  place_id: string;
  content_type: UploadContentType;
  file_size_mb: number;
}

export interface UploadRequestResponse {
  image_id: string;
  upload_url: string;
}

export interface UploadStatusResponse {
  status: UploadStatus;
  error: string | null;
}

export function validateUploadSize(fileSizeBytes: number): number {
  if (!Number.isFinite(fileSizeBytes) || fileSizeBytes <= 0) {
    throw new Error('Invalid file size');
  }
  const sizeMb = fileSizeBytes / (1024 * 1024);
  if (sizeMb > MAX_UPLOAD_MB) {
    throw new Error(`Image too large (max ${MAX_UPLOAD_MB}MB)`);
  }
  return sizeMb;
}

export async function requestUpload(
  payload: UploadRequestPayload,
): Promise<UploadRequestResponse> {
  const { data } = await client.post<UploadRequestResponse>(
    '/api/v1/upload/request',
    payload,
  );
  return data;
}

export async function confirmUpload(image_id: string): Promise<{ ok: boolean }> {
  const { data } = await client.post<{ ok: boolean }>('/api/v1/upload/confirm', {
    image_id,
  });
  return data;
}

export async function fetchUploadStatus(image_id: string): Promise<UploadStatusResponse> {
  const { data } = await client.get<UploadStatusResponse>(
    `/api/v1/upload/status/${image_id}`,
  );
  return data;
}

// Direct-to-R2 PUT using the presigned URL — deliberately bypasses `client`
// (no baseURL, no API key / auth headers; R2 authenticates via the presign
// signature already embedded in the URL).
export async function uploadToSignedUrl(
  uploadUrl: string,
  fileUri: string,
  contentType: UploadContentType,
): Promise<void> {
  const fileResponse = await fetch(fileUri);
  const blob = await fileResponse.blob();

  const putResponse = await fetch(uploadUrl, {
    method: 'PUT',
    headers: { 'Content-Type': contentType },
    body: blob,
  });

  if (!putResponse.ok) {
    throw new Error(`Upload to storage failed (status ${putResponse.status})`);
  }
}
