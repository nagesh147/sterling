import { create } from 'zustand';
import { useQueryClient } from '@tanstack/react-query';

export type SimState = 'idle' | 'loading' | 'running' | 'paused';

export interface SimSignalEvent {
  time_iso: string;
  strategy: string;
  instrument: string;
  direction: string;
  strength: string;
  entry: number;
  stop: number;
  target: number;
}

export interface SimStats {
  signals_fired: number;
  trades_entered: number;
  wins: number;
  losses: number;
  pnl: number;
  events: SimSignalEvent[];
}

export interface SimStatus {
  state: SimState;
  config: {
    date: string;
    start_time: string;
    end_time: string;
    speed: number;
    resolution: string;
    instruments: string[];
  } | null;
  current_time_iso: string;
  progress_pct: number;
  bars_played: number;
  bars_total: number;
  stats: SimStats;
  elapsed_real_s: number;
}

interface SimulationStore {
  // UI state
  barOpen: boolean;
  setBarOpen: (open: boolean) => void;
  
  // Simulation state (from backend)
  status: SimStatus;
  setStatus: (s: SimStatus) => void;
  
  // Local form state (before starting)
  date: string;
  startTime: string;
  endTime: string;
  speed: number;
  setDate: (d: string) => void;
  setStartTime: (t: string) => void;
  setEndTime: (t: string) => void;
  setSpeed: (s: number) => void;
  
  // Summary modal
  showSummary: boolean;
  setShowSummary: (s: boolean) => void;
}

const DEFAULT_STATUS: SimStatus = {
  state: 'idle',
  config: null,
  current_time_iso: '',
  progress_pct: 0,
  bars_played: 0,
  bars_total: 0,
  stats: { signals_fired: 0, trades_entered: 0, wins: 0, losses: 0, pnl: 0, events: [] },
  elapsed_real_s: 0,
};

export const useSimulationStore = create<SimulationStore>((set) => ({
  barOpen: false,
  setBarOpen: (open) => set({ barOpen: open }),
  status: DEFAULT_STATUS,
  setStatus: (status) => set({ status }),
  date: new Date().toISOString().slice(0, 10),
  startTime: '09:15:00',
  endTime: '15:30:00',
  speed: 5,
  setDate: (date) => set({ date }),
  setStartTime: (startTime) => set({ startTime }),
  setEndTime: (endTime) => set({ endTime }),
  setSpeed: (speed) => set({ speed }),
  showSummary: false,
  setShowSummary: (showSummary) => set({ showSummary }),
}));

// ── API helpers ──
const API = '/api/v1/simulation';

async function post<T = SimStatus>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function useSimulation() {
  const store = useSimulationStore();
  const { setStatus, setShowSummary } = store;

  let queryClient: ReturnType<typeof useQueryClient> | null = null;
  try {
    queryClient = useQueryClient();
  } catch {
    /* safely fallback when rendered outside QueryClientProvider in isolated tests */
  }

  const start = async () => {
    const config = {
      date: store.date,
      start_time: store.startTime,
      end_time: store.endTime,
      speed: store.speed,
      resolution: '5m',
      instruments: [],
    };
    try {
      const status = await post('/start', config);
      setStatus(status);
      queryClient?.invalidateQueries();
      window.dispatchEvent(new CustomEvent('sterling-simulation-start'));
      startPolling();
    } catch (err) {
      console.warn('Simulation start failed, stopping prior session and retrying:', err);
      try {
        await post('/stop');
        const status = await post('/start', config);
        setStatus(status);
        queryClient?.invalidateQueries();
        window.dispatchEvent(new CustomEvent('sterling-simulation-start'));
        startPolling();
      } catch (retryErr) {
        console.error('Simulation start failed:', retryErr);
      }
    }
  };

  const stop = async () => {
    const status = await post('/stop');
    setStatus(status);
    queryClient?.invalidateQueries();
    stopPolling();
    if (store.status.stats.signals_fired > 0) {
      setShowSummary(true);
    }
  };

  const pause = async () => {
    const status = await post('/pause');
    setStatus(status);
  };

  const resume = async () => {
    const status = await post('/resume');
    setStatus(status);
  };

  const setSpeed = async (speed: number) => {
    store.setSpeed(speed);
    if (store.status.state === 'running' || store.status.state === 'paused') {
      const status = await post('/speed', { speed });
      setStatus(status);
    }
  };

  return { ...store, start, stop, pause, resume, setSpeed };
}

// ── Polling for status updates ──
let pollInterval: ReturnType<typeof setInterval> | null = null;

function startPolling() {
  stopPolling();
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/v1/simulation/status');
      if (res.ok) {
        const status: SimStatus = await res.json();
        useSimulationStore.getState().setStatus(status);
        // Auto-stop polling when simulation ends
        if (status.state === 'idle' && useSimulationStore.getState().status.state !== 'idle') {
          stopPolling();
          if (status.stats.signals_fired > 0) {
            useSimulationStore.getState().setShowSummary(true);
          }
        }
      }
    } catch { /* ignore polling errors */ }
  }, 150);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

// Convenience selectors
export const useSimActive = () => useSimulationStore(s => s.status.state !== 'idle');
export const useSimBarOpen = () => useSimulationStore(s => s.barOpen);
