import axios from 'axios';

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';
const API_KEY = process.env.EXPO_PUBLIC_API_KEY ?? '';

export const client = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    ...(API_KEY ? { 'x-api-key': API_KEY } : {}),
  },
});

client.interceptors.request.use((config) => {
  const requestId = Math.random().toString(36).slice(2) + Date.now().toString(36);
  config.headers['X-Request-ID'] = requestId;
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 429) {
      error.message = 'Rate limit reached. Please wait a moment.';
    }
    return Promise.reject(error);
  },
);
