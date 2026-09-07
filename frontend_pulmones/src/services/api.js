import axios from 'axios';

// Permitir desarrollo local y producción sin cambiar el código manualmente.
export const API_BASE_URL = import.meta.env.VITE_API_URL
  || (import.meta.env.DEV ? 'http://localhost:8001/api' : 'https://pulmnooon.onrender.com/api');

const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

const normalizeAssetUrl = (url) => {
  if (!url) return url;
  try {
    // La URL ya viene absoluta y correcta desde el backend (slices2dUrls / model3dUrl).
    // Solo le agregamos el parámetro de cache-busting, sin tocar protocolo ni host:
    // reescribirlos acá pisaba la URL correcta con la de VITE_API_URL si esta
    // quedaba mal configurada (por ejemplo, con un puerto que no corresponde en Render).
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