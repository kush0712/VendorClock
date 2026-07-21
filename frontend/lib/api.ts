import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('vc_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('vc_token');
      localStorage.removeItem('vc_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  },
);

// ─── API helpers ─────────────────────────────────────────────────────────────

export const dashboardApi = {
  getSummary: () => api.get('/api/dashboard/summary').then(r => r.data),
  getPriorityQueue: () => api.get('/api/dashboard/priority-queue').then(r => r.data),
  getByVendor: () => api.get('/api/dashboard/by-vendor').then(r => r.data),
};

export const invoicesApi = {
  list: (params?: Record<string, unknown>) => api.get('/api/invoices/', { params }).then(r => r.data),
  get: (id: number) => api.get(`/api/invoices/${id}`).then(r => r.data),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/api/invoices/${id}`, data).then(r => r.data),
};

export const vendorsApi = {
  list: (params?: Record<string, unknown>) => api.get('/api/vendors/', { params }).then(r => r.data),
  get: (id: number) => api.get(`/api/vendors/${id}`).then(r => r.data),
  getDeclaration: (token: string) => api.get(`/api/vendors/declaration/${token}`).then(r => r.data),
  sendDeclaration: (id: number) => api.post(`/api/vendors/${id}/send-declaration`).then(r => r.data),
};

export const ingestionApi = {
  upload: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api.post('/api/ingestion/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data);
  },
  getStatus: (id: number) => api.get(`/api/ingestion/${id}/status`).then(r => r.data),
  list: () => api.get('/api/ingestion/').then(r => r.data),
  remap: (id: number, mapping: Record<string, string | null>) =>
    api.post(`/api/ingestion/${id}/remap`, { column_mapping: mapping }).then(r => r.data),
};

export const exportsApi = {
  form3cd: async (fy?: string) => {
    const token = localStorage.getItem('vc_token');
    const url = new URL('/api/exports/form-3cd', API_URL);
    if (fy) url.searchParams.set('fy', fy);
    const res = await fetch(url.toString(), {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('Export failed');
    const rawBlob = await res.blob();
    // Explicitly set MIME type so the browser saves with .xlsx extension
    return new Blob([rawBlob], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  },
  msme1: async (halfYear?: string) => {
    const token = localStorage.getItem('vc_token');
    const url = new URL('/api/exports/msme-1', API_URL);
    if (halfYear) url.searchParams.set('half_year', halfYear);
    const res = await fetch(url.toString(), {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('Export failed');
    const rawBlob = await res.blob();
    // Explicitly set MIME type so the browser saves with .xlsx extension
    return new Blob([rawBlob], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  },
};

export const settingsApi = {
  getStatus: () => api.get('/api/settings/status').then(r => r.data),
  testEmail: (recipient?: string) =>
    api.post('/api/settings/test-email', { recipient: recipient || '' }).then(r => r.data),
  updateRecipient: (alertEmail: string, slackWebhookUrl?: string) =>
    api.post('/api/settings/update-recipient', {
      alert_email: alertEmail,
      slack_webhook_url: slackWebhookUrl || '',
    }).then(r => r.data),
};

export function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

