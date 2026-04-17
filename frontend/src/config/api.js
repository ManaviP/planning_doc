const trimTrailingSlashes = (value) => String(value || '').replace(/\/+$/, '');

const localDefaultApi = 'http://localhost:8000';

const configuredApiBase = trimTrailingSlashes(import.meta.env.VITE_API_BASE_URL);

export const API_BASE_URL = configuredApiBase
  || (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? localDefaultApi
    : localDefaultApi);

const configuredWsBase = trimTrailingSlashes(import.meta.env.VITE_WS_BASE_URL);

export const WS_BASE_URL = configuredWsBase
  || API_BASE_URL.replace(/^http/i, 'ws');

export const apiUrl = (path) => {
  const normalizedPath = String(path || '').startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

export const wsUrl = (path) => {
  const normalizedPath = String(path || '').startsWith('/') ? path : `/${path}`;
  return `${WS_BASE_URL}${normalizedPath}`;
};
