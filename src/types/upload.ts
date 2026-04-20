export type UploadRequest = {
  place_id: string;
  content_type: 'image/jpeg';
  file_size_mb: number;
};

export type UploadResponse = {
  image_id: string;
  upload_url: string;
};

export type UploadStatus = 'pending' | 'processing' | 'ready' | 'failed';

export type UploadStatusResponse = {
  status: UploadStatus;
  error?: string | null;
};
