const trimTrailingSlashes = (value) => String(value || '').replace(/\/+$/, '');

const isLocalHost =
  typeof window !== 'undefined'
  && (window.location.hostname === 'localhost'
    || window.location.hostname === '127.0.0.1'
    || window.location.hostname === '::1');

const localDefaultApi = 'http://localhost:8000';

const configuredApiBase = trimTrailingSlashes(import.meta.env.VITE_API_BASE_URL);

export const API_BASE_URL = configuredApiBase
  || (isLocalHost ? localDefaultApi : '');

const configuredWsBase = trimTrailingSlashes(import.meta.env.VITE_WS_BASE_URL);

export const WS_BASE_URL = configuredWsBase
  || (isLocalHost
    ? 'ws://localhost:8000'
    : '');

export const apiUrl = (path) => {
  const normalizedPath = String(path || '').startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

export const wsUrl = (path) => {
  const normalizedPath = String(path || '').startsWith('/') ? path : `/${path}`;
  return `${WS_BASE_URL}${normalizedPath}`;
};
