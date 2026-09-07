import axios from 'axios';

// Permitir desarrollo local y producción de forma automática y segura.
// Si estamos en un dominio web real (producción), apunta a Render; si estamos en la PC, a localhost.
const isProduction = typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';

export const API_BASE_URL = import.meta.env.VITE_API_URL || (
  isProduction 
    ? 'https://pulmnooon.onrender.com/api' 
    : 'http://localhost:8001/api'
);

const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

const normalizeAssetUrl = (url) => {
  if (!url) return url;
  try {
    // La URL ya viene absoluta y correcta desde el backend (slices2dUrls / model3dUrl).
    // Solo le agregamos el parámetro de cache-busting, sin tocar protocolo ni host.
    const parsed = new URL(url);
    parsed.searchParams.set('v', Date.now().toString());
    return parsed.toString();
  } catch {
    return url;
  }
};

export const uploadZipFile = async (file) => {
  console.info('[API] Subiendo ZIP', { name: file.name, size: file.size, type: file.type });
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await apiClient.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  // Es vital retornar response.data para que el Dashboard reciba el task_id
  return response.data; 
};

export const checkTaskStatus = async (taskId) => {
  console.info('[API] Consultando tarea', taskId);
  const response = await apiClient.get(`/status/${taskId}`);
  console.info('[API] Estado recibido', response.data);
  if (response.data.status === 'completed' && response.data.results) {
    response.data.results.model3dUrl = normalizeAssetUrl(response.data.results.model3dUrl);
    response.data.results.slices2dUrls = (response.data.results.slices2dUrls || []).map(normalizeAssetUrl);
  }
  return response.data;
};

export const validateWithGemini = async (taskId) => {
  const response = await apiClient.post(`/validate-gemini/${taskId}`);
  return response.data;
};