import { useStore } from '../store/useStore';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const host = useStore.getState().apiHost;
  const resp = await fetch(`${host}${path}`, options);
  
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    let msg = `HTTP ${resp.status}`;
    if (err && typeof err === 'object' && 'detail' in err) {
      if (typeof err.detail === 'string') {
        msg = err.detail;
      } else if (typeof err.detail === 'object' && err.detail !== null) {
        msg = JSON.stringify(err.detail);
      }
    }
    throw new Error(msg);
  }
  
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

const json = (body: unknown) => ({
  headers: { 'Content-Type': 'application/json' },
  body: body !== undefined ? JSON.stringify(body) : undefined,
});

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', ...json(body) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', ...json(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', ...json(body) }),
  delete: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'DELETE', ...(body !== undefined ? json(body) : {}) }),
};
