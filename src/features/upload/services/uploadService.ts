import { apiClient } from '@/data/client/apiClient';
import {
  UploadRequest,
  UploadResponse,
  UploadStatusResponse,
} from '@/types/upload';

export const requestUpload = async (
  payload: UploadRequest
): Promise<UploadResponse> => {
  return apiClient('/v1/upload/request', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
};

export const confirmUpload = async (image_id: string) => {
  return apiClient('/v1/upload/confirm', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ image_id }),
  });
};

export const fetchUploadStatus = async (
  image_id: string
): Promise<UploadStatusResponse> => {
  return apiClient(`/v1/upload/status/${image_id}`);
};