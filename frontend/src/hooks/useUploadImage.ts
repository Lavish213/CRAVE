import {
  ALLOWED_UPLOAD_TYPES,
  PhotoType,
  UploadContentType,
  confirmUpload,
  requestUpload,
  uploadToSignedUrl,
  validateUploadSize,
} from '../api/upload';

interface LocalImage {
  uri: string;
  fileSize?: number;
  mimeType?: string;
}

function resolveContentType(mimeType?: string): UploadContentType {
  if (mimeType && (ALLOWED_UPLOAD_TYPES as readonly string[]).includes(mimeType)) {
    return mimeType as UploadContentType;
  }
  return 'image/jpeg';
}

export const useUploadImage = () => {
  const upload = async (
    image: LocalImage,
    place_id: string,
    photo_type: PhotoType = 'food',
  ): Promise<string> => {
    if (!image.fileSize) {
      throw new Error('Missing file size');
    }

    const fileSizeMb = validateUploadSize(image.fileSize);
    const content_type = resolveContentType(image.mimeType);

    try {
      // 1. Request a signed upload URL
      const { image_id, upload_url } = await requestUpload({
        place_id,
        content_type,
        file_size_mb: fileSizeMb,
        photo_type,
      });

      // 2. Upload directly to R2
      await uploadToSignedUrl(upload_url, image.uri, content_type);

      // 3. Confirm — backend queues async processing
      await confirmUpload(image_id);

      return image_id;
    } catch (err) {
      if (__DEV__) console.error('[UPLOAD ERROR]', err);
      throw err;
    }
  };

  return { upload };
};
