import { requestUpload, confirmUpload } from '../services/uploadService';
import { uploadToSignedUrl } from '../services/uploadClient';
import { validateImage } from '../utils/fileValidation';
import { LocalImage } from '@/types/image';

export const useUploadImage = () => {
  const upload = async (image: LocalImage, place_id: string) => {
    if (!image.fileSize) {
      throw new Error('Missing file size');
    }

    validateImage(image.fileSize);

    const fileSizeMb = image.fileSize / (1024 * 1024);

    try {
      // 1️⃣ request signed URL
      const { image_id, upload_url } = await requestUpload({
        place_id,
        content_type: 'image/jpeg',
        file_size_mb: fileSizeMb,
      });

      // 2️⃣ upload directly to R2
      await uploadToSignedUrl(upload_url, image.uri);

      // 3️⃣ confirm upload
      await confirmUpload(image_id);

      return image_id;
    } catch (err) {
      console.error('[UPLOAD ERROR]', err);
      throw err;
    }
  };

  return { upload };
};