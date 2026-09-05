import { create } from 'zustand';
import { useQueryClient } from '@tanstack/react-query';
import { isNseClosed, shiftSessionIso } from '../lib/astro/holidays';

export type SimState = 'idle' | 'loading' | 'running' | 'paused';

export interface SimSignalEvent {
  time_iso: string;
  timestamp_ms?: number;
  strategy: string;
  instrument: string;
  direction: string;
  strength: string;
  entry: number;
  stop: number;
  target: number;
  contract?: string;
  opt_type?: string;
  strike?: number;
  spot?: number;
  premium_entry?: number;
  premium_sl?: number;
  premium_target?: number;
}

export interface SimTradeEvent {
  trade_id: string;
  entry_time_iso: string;
  exit_time_iso: string;
  timestamp_ms: number;
  strategy: string;
  symbol: string;
  underlying: string;
  direction: string;
  opt_type: string;
  strike: number;
  lots: number;
  quantity: number;
  entry_price: number;
  exit_price?: number | null;
  stop_loss: number;
  target_price: number;
  status: string;
  pnl_usd: number;
  pnl_pct: number;
  duration_mins: number;
  slippage?: number;
  raw_entry?: number | null;
  raw_exit?: number | null;
}

export interface SimStats {
  signals_fired: number;
  trades_entered: number;
  wins: number;
  losses: number;
  pnl: number;
  events: SimSignalEvent[];
  trades?: SimTradeEvent[];
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
    friction_mode?: 'realistic' | 'ideal';
    slippage_bps?: number;
  } | null;
  current_time_iso: string;
  progress_pct: number;
  bars_played: number;
  bars_total: number;
  stats: SimStats;
  elapsed_real_s: number;
  status_message: string;
  last_signal: SimSignalEvent | null;
}

export function getIstDateParts(d: Date = new Date()): { year: number; month: number; day: number; dayOfWeek: number; hours: number; minutes: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    weekday: 'short',
    hour: 'numeric',
    minute: 'numeric',
    hour12: false,
  }).formatToParts(d);
  
  const map: Record<string, string> = {};
  for (const p of parts) map[p.type] = p.value;
  
  const year = parseInt(map.year, 10);
  const month = parseInt(map.month, 10);
  const day = parseInt(map.day, 10);
  const hours = parseInt(map.hour, 10);
  const minutes = parseInt(map.minute, 10);
  
  const weekdayMap: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
  const dayOfWeek = weekdayMap[map.weekday] ?? d.getDay();
  
  return { year, month, day, dayOfWeek, hours, minutes };
}

export function formatYmd(year: number, month: number, day: number): string {
  const mm = String(month).padStart(2, '0');
  const dd = String(day).padStart(2, '0');
  return `${year}-${mm}-${dd}`;
}

/**
 * Returns the last working day of the Indian market in YYYY-MM-DD format (IST).
 * Skips weekends (Saturday/Sunday) and official NSE holidays.
 * Before 9:00 AM IST on a weekday, market has not yet opened, so it steps back.
 */
export function getLastMarketWorkingDay(refDate: Date = new Date()): string {
  const ist = getIstDateParts(refDate);
  const target = new Date(Date.UTC(ist.year, ist.month - 1, ist.day, 12, 0, 0));
  
  // If today is a trading day (Mon-Fri and not holiday), the "last completed working day"
  // is the previous trading session before today.
  const todayIso = formatYmd(ist.year, ist.month, ist.day);
  if (ist.dayOfWeek >= 1 && ist.dayOfWeek <= 5 && !isNseClosed(todayIso)) {
    target.setUTCDate(target.getUTCDate() - 1);
  }
  
  // Step back through weekends and NSE trading holidays
  while (
    target.getUTCDay() === 0 || 
    target.getUTCDay() === 6 || 
    isNseClosed(formatYmd(target.getUTCFullYear(), target.getUTCMonth() + 1, target.getUTCDate()))
  ) {
    target.setUTCDate(target.getUTCDate() - 1);
  }
  
  return formatYmd(target.getUTCFullYear(), target.getUTCMonth() + 1, target.getUTCDate());
}

/**
 * Returns today's market date in YYYY-MM-DD format (IST).
 */
export function getTodayMarketDate(refDate: Date = new Date()): string {
  const ist = getIstDateParts(refDate);
  return formatYmd(ist.year, ist.month, ist.day);
}

/**
 * Returns yesterday's date in YYYY-MM-DD format (IST).
 */
export function getYesterdayMarketDate(refDate: Date = new Date()): string {
  const ist = getIstDateParts(refDate);
  const d = new Date(Date.UTC(ist.year, ist.month - 1, ist.day, 12, 0, 0));
  d.setUTCDate(d.getUTCDate() - 1);
  return formatYmd(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
}

export interface MarketDatePreset {
  id: string;
  label: string;
  date: string;
  description: string;
}

/**
 * Generates dynamically filtered market presets based on the current market status.
 * - Never shows "Today" if today is a weekend, holiday, or before 09:00 AM.
 * - Never shows "Yesterday" if yesterday was a weekend, holiday, or identical to Last Working Day.
 * - If today is a weekend/holiday, provides "Last Working Day" and "Prev Session" so traders always have valid session options.
 */
export function getDynamicMarketPresets(refDate: Date = new Date()): MarketDatePreset[] {
  const ist = getIstDateParts(refDate);
  const todayIso = formatYmd(ist.year, ist.month, ist.day);
  const yesterdayTarget = new Date(Date.UTC(ist.year, ist.month - 1, ist.day, 12, 0, 0));
  yesterdayTarget.setUTCDate(yesterdayTarget.getUTCDate() - 1);
  const yesterdayIso = formatYmd(yesterdayTarget.getUTCFullYear(), yesterdayTarget.getUTCMonth() + 1, yesterdayTarget.getUTCDate());

  const lastWorkingDay = getLastMarketWorkingDay(refDate);
  const presets: MarketDatePreset[] = [];

  // Preset 1: Last Working Day (always valid)
  presets.push({
    id: 'lastWorkingDay',
    label: '📅 Last Working Day',
    date: lastWorkingDay,
    description: `Last completed market session (${lastWorkingDay})`,
  });

  // Preset 2: Today (ONLY if today is an active market day, NOT a weekend/holiday, and after 09:00 AM IST)
  const isTodayTradingDay = !isNseClosed(todayIso);
  const isAfterMarketOpen = ist.hours > 9 || (ist.hours === 9 && ist.minutes >= 0);
  if (isTodayTradingDay && isAfterMarketOpen && todayIso !== lastWorkingDay) {
    presets.push({
      id: 'today',
      label: 'Today',
      date: todayIso,
      description: `Today's market session (${todayIso})`,
    });
  }

  // Preset 3: Yesterday (ONLY if yesterday was an active market day, NOT a weekend/holiday, and distinct from Last Working Day)
  const isYesterdayTradingDay = !isNseClosed(yesterdayIso);
  if (isYesterdayTradingDay && yesterdayIso !== lastWorkingDay && yesterdayIso !== todayIso) {
    presets.push({
      id: 'yesterday',
      label: 'Yesterday',
      date: yesterdayIso,
      description: `Yesterday's market session (${yesterdayIso})`,
    });
  }

  // Preset 4: If today is a weekend or holiday, and we only have 1 preset (Last Working Day),
  // provide "Prev Session" as an additional quick option.
  if (presets.length === 1) {
    const prevSession = shiftSessionIso(lastWorkingDay, -1);
    presets.push({
      id: 'prevSession',
      label: 'Prev Session',
      date: prevSession,
      description: `Prior market session before ${lastWorkingDay} (${prevSession})`,
    });
  }

  return presets;
}

export type SimViewMode = 'half' | 'full' | 'fullheight' | 'maximized' | 'fullscreen';

interface SimulationStore {
  // UI state
  barOpen: boolean;
  setBarOpen: (open: boolean) => void;
  viewMode: SimViewMode;
  setViewMode: (v: SimViewMode) => void;
  activeDockTab: 'config' | 'signals' | 'trades' | 'split';
  setActiveDockTab: (t: 'config' | 'signals' | 'trades' | 'split') => void;
  
  // Simulation state (from backend)
  status: SimStatus;
  setStatus: (s: SimStatus) => void;
  
  // Local form state (before starting)
  date: string;
  endDate: string;
  startTime: string;
  endTime: string;
  speed: number;
  frictionMode: 'realistic' | 'ideal';
  selectedStrategy: string;
  selectedStrategies: string[];
  lots: number;
  moneyness: string;
  selectedMoneyness: string[];
  setDate: (d: string) => void;
  setEndDate: (d: string) => void;
  setStartTime: (t: string) => void;
  setEndTime: (t: string) => void;
  setSpeed: (s: number) => void;
  setFrictionMode: (f: 'realistic' | 'ideal') => void;
  setSelectedStrategy: (s: string) => void;
  setSelectedStrategies: (s: string[]) => void;
  toggleStrategy: (s: string) => void;
  setLots: (l: number) => void;
  setMoneyness: (m: string) => void;
  setSelectedMoneyness: (m: string[]) => void;
  toggleMoneyness: (m: string) => void;
  frictionMode: 'realistic' | 'ideal';
  setFrictionMode: (m: 'realistic' | 'ideal') => void;
  
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
  status_message: '',
  last_signal: null,
};

const initialDate = getLastMarketWorkingDay();

export const useSimulationStore = create<SimulationStore>((set) => ({
  barOpen: false,
  setBarOpen: (open) => set({ barOpen: open }),
  viewMode: 'half',
  setViewMode: (viewMode) => set({ viewMode }),
  activeDockTab: 'split',
  setActiveDockTab: (activeDockTab) => set({ activeDockTab }),
  status: DEFAULT_STATUS,
  setStatus: (status) => set({ status }),
  date: initialDate,
  endDate: initialDate,
  startTime: '09:00:00',
  endTime: '15:30:00',
  speed: 5,
  frictionMode: 'realistic',
  selectedStrategy: 'all',
  selectedStrategies: ['all'],
  lots: 1,
  moneyness: 'ATM',
  selectedMoneyness: ['ATM'],
  frictionMode: 'realistic',
  setFrictionMode: (frictionMode) => set({ frictionMode }),
  setDate: (date) => set({ date }),
  setEndDate: (endDate) => set({ endDate }),
  setStartTime: (startTime) => set({ startTime }),
  setEndTime: (endTime) => set({ endTime }),
  setSpeed: (speed) => set({ speed }),
  setFrictionMode: (frictionMode) => set({ frictionMode }),
  setSelectedStrategy: (selectedStrategy) => set({ selectedStrategy, selectedStrategies: [selectedStrategy] }),
  setSelectedStrategies: (selectedStrategies) => set({ selectedStrategies, selectedStrategy: selectedStrategies.length === 1 ? selectedStrategies[0] : (selectedStrategies.includes('all') ? 'all' : selectedStrategies.join(',')) }),
  toggleStrategy: (stratKey: string) => set((state) => {
    if (stratKey === 'all') {
      return { selectedStrategies: ['all'], selectedStrategy: 'all' };
    }
    const current = state.selectedStrategies.filter(s => s !== 'all');
    let next: string[];
    if (current.includes(stratKey)) {
      next = current.filter(s => s !== stratKey);
      if (next.length === 0) next = ['all'];
    } else {
      next = [...current, stratKey];
    }
    return {
      selectedStrategies: next,
      selectedStrategy: next.length === 1 ? next[0] : (next.includes('all') ? 'all' : next.join(',')),
    };
  }),
  setLots: (lots) => set({ lots }),
  setMoneyness: (moneyness) => set({ moneyness, selectedMoneyness: [moneyness] }),
  setSelectedMoneyness: (selectedMoneyness) => set({ selectedMoneyness, moneyness: selectedMoneyness.join(',') }),
  toggleMoneyness: (legKey: string) => set((state) => {
    if (legKey === 'ALL') {
      return { selectedMoneyness: ['ALL'], moneyness: 'ALL' };
    }
    const current = state.selectedMoneyness.filter(m => m !== 'ALL');
    let next: string[];
    if (current.includes(legKey)) {
      next = current.filter(m => m !== legKey);
      if (next.length === 0) next = ['ALL'];
    } else {
      next = [...current, legKey];
    }
    return {
      selectedMoneyness: next,
      moneyness: next.length === 1 ? next[0] : (next.includes('ALL') ? 'ALL' : next.join(',')),
    };
  }),
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
  const queryClient = useQueryClient();

  const clearLocalFeedCache = () => {
    try {
      sessionStorage.removeItem('sterling_signal_feed_v3');
      sessionStorage.removeItem('sterling_signal_states_v3');
    } catch { /* quota */ }
  };

  const start = async () => {
    const config = {
      date: store.date,
      end_date: store.endDate,
      start_time: store.startTime,
      end_time: store.endTime,
      speed: store.speed,
      resolution: '5m',
      instruments: [],
      strategy: store.selectedStrategy,
      strategies: store.selectedStrategies,
      lots: store.lots,
      moneyness: store.moneyness,
      friction_mode: store.frictionMode,

    };
    clearLocalFeedCache();
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
        clearLocalFeedCache();
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
    clearLocalFeedCache();
    const status = await post('/stop');
    setStatus(status);
    queryClient?.invalidateQueries();
    stopPolling();
    if (status.stats.signals_fired > 0) {
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

  const stepBars = async (count: number) => {
    if (store.status.state !== 'idle') {
      const status = await post('/seek', { bars_offset: count });
      setStatus(status);
    }
  };

  const jumpStart = async () => {
    if (store.status.state !== 'idle') {
      const status = await post('/seek', { action: 'jump_start' });
      setStatus(status);
    }
  };

  const jumpEnd = async () => {
    if (store.status.state !== 'idle') {
      const status = await post('/seek', { action: 'jump_end' });
      setStatus(status);
    }
  };

  const syncStatus = async () => {
    try {
      const res = await fetch('/api/v1/simulation/status');
      if (res.ok) {
        const status: SimStatus = await res.json();
        setStatus(status);
        if (status.state === 'running' || status.state === 'paused') {
          startPolling();
        }
        return status;
      }
    } catch { /* ignore */ }
    return null;
  };

  return { ...store, start, stop, pause, resume, setSpeed, stepBars, jumpStart, jumpEnd, syncStatus };
}

export { startPolling, stopPolling };

// ── Polling for status updates ──
let pollInterval: ReturnType<typeof setInterval> | null = null;

function startPolling() {
  stopPolling();
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/v1/simulation/status');
      if (res.ok) {
        const status: SimStatus = await res.json();
        const prevState = useSimulationStore.getState().status.state;
        useSimulationStore.getState().setStatus(status);
        // Auto-stop polling when simulation ends
        if (status.state === 'idle' && prevState !== 'idle') {
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
export function getSimNowMs(status: SimStatus): number | null {
  if (status.state === 'idle' || !status.config?.date || !status.current_time_iso) {
    return null;
  }
  const dateStr = status.config.date;
  const timeStr = status.current_time_iso;
  const isoStr = `${dateStr}T${timeStr}+05:30`;
  const ms = Date.parse(isoStr);
  return isNaN(ms) ? null : ms;
}

export const useSimNowMs = (): number | null => {
  const status = useSimulationStore((s) => s.status);
  return getSimNowMs(status);
};

export function useEffectiveNowMs(): number {
  const status = useSimulationStore((s) => s.status);
  const simMs = getSimNowMs(status);
  return simMs ?? Date.now();
}
