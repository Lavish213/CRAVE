// Requires the `expo-image-picker` dependency, which is not yet installed
// in frontend/package.json. Run `npx expo install expo-image-picker` to add
// it at the SDK-54-compatible version before this hook will resolve/build.
import * as ImagePicker from 'expo-image-picker';

export interface LocalImage {
  uri: string;
  width: number;
  height: number;
  fileSize: number;
  mimeType?: string;
}

export const useImagePicker = () => {
  const pick = async (): Promise<LocalImage | null> => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (!permission.granted) {
      throw new Error('Permission to access photos is required');
    }

    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
      allowsEditing: false,
    });

    if (res.canceled || !res.assets?.length) return null;

    const asset = res.assets[0];

    if (!asset.fileSize) {
      throw new Error('Could not determine file size');
    }

    return {
      uri: asset.uri,
      width: asset.width,
      height: asset.height,
      fileSize: asset.fileSize,
      mimeType: asset.mimeType,
    };
  };

  return { pick };
};
