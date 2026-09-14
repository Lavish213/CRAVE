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

// Separate from UploadStatus above, which only tracks the processing
// pipeline (ready/failed) -- a photo can finish processing successfully
// (status: "ready") and still be invisible, sitting held for a human
// review. Without checking this too, "ready" alone can't distinguish a
// genuinely live photo from one silently withheld.
export type ModerationStatus = 'approved' | 'pending_review' | 'rejected';

// What the photo shows. "menu" triggers OCR extraction on the backend
// (see backend/app/services/menu/ocr/menu_photo_ocr.py) instead of just
// adding it to the general gallery.
export type PhotoType = 'food' | 'menu';

export interface UploadRequestPayload {
  place_id: string;
  content_type: UploadContentType;
  file_size_mb: number;
  photo_type?: PhotoType;
}

export interface UploadRequestResponse {
  image_id: string;
  upload_url: string;
}

export interface UploadStatusResponse {
  status: UploadStatus;
  error: string | null;
  moderation_status: ModerationStatus;
  moderation_reason: string | null;
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
//
// XMLHttpRequest, not fetch: RN's fetch has no way to observe request
// (upload) body progress, only response-download progress. `onProgress`
// receives a 0-1 fraction, not a 0-100 percentage, leaving the display
// format to the caller. See videos.ts's uploadVideoToSignedUrl for the
// same pattern applied to the (much larger) video upload.
export function uploadToSignedUrl(
  uploadUrl: string,
  fileUri: string,
  contentType: UploadContentType,
  onProgress?: (fraction: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    fetch(fileUri)
      .then((fileResponse) => fileResponse.blob())
      .then((blob) => {
        const xhr = new XMLHttpRequest();
        xhr.open('PUT', uploadUrl);
        xhr.setRequestHeader('Content-Type', contentType);

        xhr.upload.onprogress = (event) => {
          if (!onProgress || !event.lengthComputable || event.total <= 0) return;
          onProgress(event.loaded / event.total);
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`Upload to storage failed (status ${xhr.status})`));
          }
        };

        xhr.onerror = () => reject(new Error('Upload to storage failed (network error)'));
        xhr.onabort = () => reject(new Error('Upload to storage was aborted'));

        xhr.send(blob);
      })
      .catch(reject);
  });
}
