// GPS-based "find and add a new spot" flow.
// See backend/app/api/v1/routes/nearby.py for the full concept — a live,
// tight-radius Google Places search centered on the user's exact location,
// cross-referenced against places CRAVE already has. Confirming a genuinely
// new spot feeds the same discovery-candidate pipeline as unmatched social
// shares and hitlist suggestions, not a separate system.
import { client } from './client';

export interface NearbyCandidate {
  external_id: string | null;
  name: string;
  address: string | null;
  lat: number;
  lng: number;
  category_hint: string | null;
  distance_m: number;
  already_in_crave: boolean;
  place_id: string | null;
}

export interface NearbySearchResponse {
  results: NearbyCandidate[];
}

export async function searchNearby(lat: number, lng: number): Promise<NearbyCandidate[]> {
  const { data } = await client.post<NearbySearchResponse>('/api/v1/nearby/search', { lat, lng });
  return data.results;
}

export interface ConfirmNewSpotPayload {
  external_id?: string | null;
  name: string;
  lat: number;
  lng: number;
  address?: string | null;
  category_hint?: string | null;
}

export interface ConfirmNewSpotResponse {
  status: string;
  candidate_id: string;
  confidence_score: number;
}

export async function confirmNewSpot(payload: ConfirmNewSpotPayload): Promise<ConfirmNewSpotResponse> {
  const { data } = await client.post<ConfirmNewSpotResponse>('/api/v1/nearby/confirm', payload);
  return data;
}
