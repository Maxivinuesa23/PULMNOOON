import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8001',
});

const API_ORIGIN = 'http://localhost:8001';

const normalizeAssetUrl = (url) => {
  if (!url) return url;
  try {
    const parsed = new URL(url, API_ORIGIN);
    parsed.protocol = new URL(API_ORIGIN).protocol;
    parsed.host = new URL(API_ORIGIN).host;
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
  
  const response = await apiClient.post('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  // Es vital retornar response.data para que el Dashboard reciba el task_id
  return response.data; 
};

export const checkTaskStatus = async (taskId) => {
  console.info('[API] Consultando tarea', taskId);
  const response = await apiClient.get(`/api/status/${taskId}`);
  console.info('[API] Estado recibido', response.data);
  if (response.data.status === 'completed' && response.data.results) {
    response.data.results.model3dUrl = normalizeAssetUrl(response.data.results.model3dUrl);
    response.data.results.slices2dUrls = (response.data.results.slices2dUrls || []).map(normalizeAssetUrl);
  }
  return response.data;
};

export const validateWithGemini = async (taskId) => {
  const response = await apiClient.post(`/api/validate-gemini/${taskId}`);
  return response.data;
};