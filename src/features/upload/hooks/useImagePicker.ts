import * as ImagePicker from 'expo-image-picker';
import { LocalImage } from '@/types/image';

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
    };
  };

  return { pick };
};