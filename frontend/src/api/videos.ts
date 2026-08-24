// Short food-video upload — request a signed R2 URL, PUT the file
// directly to storage, then confirm so the scheduler-driven worker picks
// it up for compression/food-scoring/approval (see backend
// app/services/video/video_processing_worker.py -- deliberately NOT a
// FastAPI background task the way photo processing is, since that's real
// CPU work this app already keeps off the request-serving process).
//
// Mirrors src/api/upload.ts's request/confirm shape and direct-to-R2 PUT
// pattern (see backend/app/api/v1/routes/videos.py for the real contract).
import { client } from './client';

export const ALLOWED_VIDEO_CONTENT_TYPES = [
  'video/mp4',
  'video/quicktime',
  'video/webm',
] as const;
export type VideoContentType = (typeof ALLOWED_VIDEO_CONTENT_TYPES)[number];

export const MAX_VIDEO_UPLOAD_MB = 50;

export type VideoStatus =
  | 'pending'
  | 'queued'
  | 'processing'
  | 'approved'
  | 'rejected'
  | 'failed';

export interface VideoRequestPayload {
  place_id: string;
  content_type: VideoContentType;
  template_id?: string;
  // Client-generated id from the offline record flow (see
  // videoQueueStore.ts) -- lets a retried request after a crash/lost-
  // response find the row it already created instead of duplicating it.
  client_id?: string;
}

export interface VideoRequestResponse {
  video_id: string;
  upload_url: string;
  key: string;
}

export interface VideoStatusResponse {
  id: string;
  status: VideoStatus;
  rejectReason: string | null;
  durationMs: number | null;
  foodScore: number | null;
  thumbnailUrl: string | null;
  videoUrl: string | null;
}

export interface FeedVideo {
  id: string;
  placeId: string;
  templateId: string | null;
  durationMs: number | null;
  thumbnailUrl: string | null;
  videoUrl: string | null;
}

export interface VideoTemplate {
  id: string;
  name: string;
  overlayAssetUrl: string | null;
  beatCues: Array<{ t: number; cue: string }>;
  minFoodAreaPct: number;
}

export function validateVideoUploadSize(fileSizeBytes: number): number {
  if (!Number.isFinite(fileSizeBytes) || fileSizeBytes <= 0) {
    throw new Error('Invalid file size');
  }
  const sizeMb = fileSizeBytes / (1024 * 1024);
  if (sizeMb > MAX_VIDEO_UPLOAD_MB) {
    throw new Error(`Video too large (max ${MAX_VIDEO_UPLOAD_MB}MB)`);
  }
  return sizeMb;
}

export async function requestVideoUpload(
  payload: VideoRequestPayload,
): Promise<VideoRequestResponse> {
  const { data } = await client.post<VideoRequestResponse>('/api/v1/videos/request', payload);
  return data;
}

export async function confirmVideoUpload(videoId: string): Promise<{ ok: boolean }> {
  const { data } = await client.post<{ ok: boolean }>(`/api/v1/videos/${videoId}/confirm`);
  return data;
}

export async function fetchVideoStatus(videoId: string): Promise<VideoStatusResponse> {
  const { data } = await client.get<VideoStatusResponse>(`/api/v1/videos/${videoId}`);
  return data;
}

export async function fetchVideoFeed(opts: {
  placeId?: string;
  limit?: number;
  offset?: number;
}): Promise<{ videos: FeedVideo[]; limit: number; offset: number }> {
  const { data } = await client.get('/api/v1/videos/feed', {
    params: { place_id: opts.placeId, limit: opts.limit, offset: opts.offset },
  });
  return data;
}

export async function fetchVideoTemplates(): Promise<{ templates: VideoTemplate[] }> {
  const { data } = await client.get('/api/v1/videos/templates');
  return data;
}

// Direct-to-R2 PUT using the presigned URL — deliberately bypasses
// `client` (no baseURL, no API key/auth headers; R2 authenticates via the
// presign signature already embedded in the URL), same as upload.ts's
// uploadToSignedUrl.
export async function uploadVideoToSignedUrl(
  uploadUrl: string,
  fileUri: string,
  contentType: VideoContentType,
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
