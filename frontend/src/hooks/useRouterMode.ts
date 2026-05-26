import { useCallback, useEffect, useState } from 'react';
import { api } from '../utils/api';

/**
 * Single source of truth for the three trading modes — paper / shadow / live.
 *
 * The authoritative value lives in the backend (`/api/v1/trading/algo-router-mode`,
 * persisted to app.state + config). We mirror it into localStorage
 * (`sterling.routerMode`) and broadcast a `sterling-router-mode-change` event so
 * every mounted view (LiveControlPanel, scalping tab, V4 dashboard) stays in sync
 * without prop drilling.
 *
 *   paper  — no exchange call, pure simulation
 *   shadow — keys present, but orders are simulated (paper position, no real fill)
 *   live   — real orders on the exchange
 */
export type RouterMode = 'paper' | 'shadow' | 'live';

const KEY = 'sterling.routerMode';
const EVT = 'sterling-router-mode-change';

function readLocal(): RouterMode {
  if (typeof window === 'undefined') return 'paper';
  const v = window.localStorage.getItem(KEY) as RouterMode | null;
  return v === 'paper' || v === 'shadow' || v === 'live' ? v : 'paper';
}

export function useRouterMode() {
  const [mode, setModeState] = useState<RouterMode>(readLocal);

  // Pull the authoritative value from the backend on mount, then keep in sync
  // with the localStorage + custom-event channel that LiveControlPanel writes.
  useEffect(() => {
    let cancelled = false;
    api.get<{ mode: string }>('/api/v1/trading/algo-router-mode')
      .then((r) => {
        if (cancelled || !r?.mode) return;
        const m = r.mode as RouterMode;
        setModeState(m);
        window.localStorage.setItem(KEY, m);
      })
      .catch(() => { /* offline → keep localStorage value */ });

    const onStorage = (e: StorageEvent) => {
      if (e.key === KEY && e.newValue) setModeState(e.newValue as RouterMode);
    };
    const onEvent = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      if (detail) setModeState(detail as RouterMode);
    };
    window.addEventListener('storage', onStorage);
    window.addEventListener(EVT, onEvent);
    return () => {
      cancelled = true;
      window.removeEventListener('storage', onStorage);
      window.removeEventListener(EVT, onEvent);
    };
  }, []);

  const setMode = useCallback(async (next: RouterMode) => {
    setModeState(next);                                   // optimistic
    window.localStorage.setItem(KEY, next);
    window.dispatchEvent(new CustomEvent(EVT, { detail: next }));
    await api.post('/api/v1/trading/algo-router-mode', { mode: next });
  }, []);

  return { mode, setMode };
}
