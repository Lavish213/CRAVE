import axios from 'axios';

export const uploadToSignedUrl = async (
  uploadUrl: string,
  fileUri: string
) => {
  const response = await fetch(fileUri);
  const blob = await response.blob();

  await axios.put(uploadUrl, blob, {
    headers: {
      'Content-Type': 'image/jpeg',
    },
  });
};