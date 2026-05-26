/**
 * Sterling v4 — LiveControlPanel
 *
 * Single panel that surfaces every safety primitive to the user:
 *   • Kill switch (toggle + reason)
 *   • Daily-loss meter (level: clear | warning | halt)
 *   • Retry queue (poisoned items in red)
 *   • Mode selector (paper / shadow / live)
 *
 * Polls every 5 s. Always visible on both Pro Terminal and Simple page so
 * operators can hit STOP regardless of which view they're on.
 */
import { useCallback, useEffect, useState } from 'react';
import { api } from '../utils/api';
import { c as t, tint } from '../styles/terminalUI';

type KillSwitch = { enabled: boolean; reason: string; set_ts_ms: number };
type DailyLoss = {
  pnl_usd: number;
  level: 'clear' | 'warning' | 'halt';
  soft_warn_usd: number;
  hard_halt_usd: number;
};
type RetryItem = {
  id: string;
  payload: Record<string, unknown>;
  attempt: number;
  max_attempts: number;
  last_error: string;
  poison: boolean;
};
type RetryQueue = { items: RetryItem[]; count: number };
type AlgoMode = { enabled: boolean };
type RouterModeResponse = { mode: string };
type ScoringStrategyResponse = { strategy: string };

type RouterMode = 'paper' | 'shadow' | 'live';
type ScoringStrategy = 'by_edge_max_linear_agree' | 'unweighted_mean';

const POLL_MS = 5_000;

const levelColor: Record<DailyLoss['level'], string> = {
  clear: t.green,
  warning: t.amber,
  halt: t.red,
};

const modeColor: Record<RouterMode, string> = {
  paper: t.dim,
  shadow: t.blue,
  live: t.red,
};

export default function LiveControlPanel() {
  const [killSwitch, setKillSwitch] = useState<KillSwitch | null>(null);
  const [dailyLoss, setDailyLoss] = useState<DailyLoss | null>(null);
  const [retryQ, setRetryQ] = useState<RetryQueue | null>(null);
  const [algoMode, setAlgoMode] = useState<AlgoMode | null>(null);
  const [routerMode, setRouterMode] = useState<RouterMode>(
    (typeof window !== 'undefined'
      ? (window.localStorage.getItem('sterling.routerMode') as RouterMode)
      : null) || 'paper',
  );
  const [scoringStrategy, setScoringStrategy] = useState<ScoringStrategy>('by_edge_max_linear_agree');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [ks, dl, rq, am, rm, ss] = await Promise.all([
        api.get<KillSwitch>('/api/v1/trading/kill-switch'),
        api.get<DailyLoss>('/api/v1/trading/daily-loss'),
        api.get<RetryQueue>('/api/v1/trading/retry-queue'),
        api.get<AlgoMode>('/api/v1/trading/algo-mode'),
        api.get<RouterModeResponse>('/api/v1/trading/algo-router-mode'),
        api.get<ScoringStrategyResponse>('/api/v1/trading/scoring-strategy'),
      ]);
      setKillSwitch(ks);
      setDailyLoss(dl);
      setRetryQ(rq);
      setAlgoMode(am);
      setRouterMode(rm.mode as RouterMode);
      setScoringStrategy(ss.strategy as ScoringStrategy);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem('sterling.routerMode', rm.mode);
      }
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, POLL_MS);
    return () => clearInterval(t);
  }, [fetchAll]);

  const toggleKill = async () => {
    if (!killSwitch) return;
    setBusy(true);
    try {
      const next = !killSwitch.enabled;
      await api.post('/api/v1/trading/kill-switch', {
        enabled: next,
        reason: next ? 'manual operator halt' : '',
      });
      await fetchAll();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const removeRetry = async (rid: string) => {
    setBusy(true);
    try {
      await api.delete(`/api/v1/trading/retry-queue/${rid}`);
      await fetchAll();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

const changeMode = async (next: RouterMode) => {
    setRouterMode(next);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('sterling.routerMode', next);
      window.dispatchEvent(new CustomEvent('sterling-router-mode-change', { detail: next }));
      window.localStorage.setItem('sterling.renderVersion', String(Date.now()));
    }
    try {
      await api.post('/api/v1/trading/algo-router-mode', { mode: next });
      await fetchAll();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const changeStrategy = async (next: ScoringStrategy) => {
    setScoringStrategy(next);
    try {
      await api.post('/api/v1/trading/scoring-strategy', { strategy: next });
      await fetchAll();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const strategyLabel = (s: ScoringStrategy): string => {
    if (s === 'by_edge_max_linear_agree') return 'EDGE.MAX';
    if (s === 'unweighted_mean') return 'UNWTD.MEAN';
    return s;
  };

  return (
    <div
      style={{
        background: t.surface,
        border: `1px solid ${t.border}`,
        borderRadius: 8,
        padding: 12,
        fontSize: 12,
        color: t.text,
        fontFamily: 'inherit',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 10,
        }}
      >
        <strong style={{ fontSize: 13 }}>LIVE CONTROL · v4</strong>
        {err && <span style={{ color: t.red }}>{err}</span>}
      </div>

      {/* ── Kill switch ─────────────────────────────────────────── */}
      <div style={row}>
        <span style={label}>Kill switch</span>
        <button
          onClick={toggleKill}
          disabled={busy}
          style={{
            background: killSwitch?.enabled ? t.red : t.green,
            color: 'white',
            border: 'none',
            padding: '4px 12px',
            borderRadius: 4,
            cursor: busy ? 'wait' : 'pointer',
            fontWeight: 600,
            minWidth: 80,
          }}
        >
          {killSwitch?.enabled ? 'HALTED' : 'ARMED'}
        </button>
      </div>
      {killSwitch?.enabled && killSwitch.reason && (
        <div style={{ ...subRow, color: t.red }}>↳ {killSwitch.reason}</div>
      )}

      {/* ── Daily loss ──────────────────────────────────────────── */}
      <div style={row}>
        <span style={label}>Daily PnL</span>
        <span
          style={{
            color: dailyLoss ? levelColor[dailyLoss.level] : t.dim,
            fontWeight: 600,
          }}
        >
          {dailyLoss
            ? `$${dailyLoss.pnl_usd.toFixed(2)} (${dailyLoss.level})`
            : '—'}
        </span>
      </div>
      {dailyLoss && (
        <div style={subRow}>
          warn ${dailyLoss.soft_warn_usd} · halt ${dailyLoss.hard_halt_usd}
        </div>
      )}

      {/* ── Mode selector ───────────────────────────────────────── */}
      <div style={row}>
        <span style={label}>Mode</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {(['paper', 'shadow', 'live'] as RouterMode[]).map((m) => (
            <button
              key={m}
              onClick={() => changeMode(m)}
              disabled={busy}
              style={{
                background: routerMode === m ? modeColor[m] : t.raised,
                color: 'white',
                border: 'none',
                padding: '4px 8px',
                borderRadius: 4,
                cursor: busy ? 'wait' : 'pointer',
                fontWeight: routerMode === m ? 600 : 400,
                textTransform: 'uppercase',
                fontSize: 10,
              }}
              title={
                m === 'paper'
                  ? 'No exchange call. Pure simulation.'
                  : m === 'shadow'
                  ? 'Live order + paper audit position. Compares fills.'
                  : 'Production trading. Real money.'
              }
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      {algoMode && routerMode === 'live' && (
        <div style={{ ...subRow, color: algoMode.enabled ? t.green : t.amber }}>
          algo_mode: {algoMode.enabled ? 'on' : 'off'}
        </div>
      )}

      {/* ── Strategy selector ─────────────────────────────────────── */}
      <div style={row}>
        <span style={label}>Strategy</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {(['by_edge_max_linear_agree', 'unweighted_mean'] as ScoringStrategy[]).map((s) => (
            <button
              key={s}
              onClick={() => changeStrategy(s)}
              disabled={busy}
              style={{
                background: scoringStrategy === s ? t.purple : t.raised,
                color: 'white',
                border: 'none',
                padding: '4px 8px',
                borderRadius: 4,
                cursor: busy ? 'wait' : 'pointer',
                fontWeight: scoringStrategy === s ? 600 : 400,
                textTransform: 'uppercase',
                fontSize: 10,
              }}
              title={
                s === 'by_edge_max_linear_agree'
                  ? 'Edge-weighted vote + max score + linear agree boost. Best from search.'
                  : 'Unweighted mean of active tracks. Legacy pre-search scoring.'
              }
            >
              {strategyLabel(s)}
            </button>
          ))}
        </div>
      </div>
      <div style={subRow}>
        {scoringStrategy === 'by_edge_max_linear_agree'
          ? 'by_edge · max · linear_agree'
          : 'unweighted · mean · none'}
      </div>

      {/* ── Retry queue ─────────────────────────────────────────── */}
      <div style={row}>
        <span style={label}>Retry queue</span>
        <span style={{ color: (retryQ?.count ?? 0) > 0 ? t.amber : t.green }}>
          {retryQ?.count ?? 0} item{(retryQ?.count ?? 0) === 1 ? '' : 's'}
        </span>
      </div>
      {(retryQ?.items ?? []).map((item) => (
        <div
          key={item.id}
          style={{
            ...subRow,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: item.poison ? tint(t.red, 22) : 'transparent',
            padding: 4,
            borderRadius: 4,
          }}
        >
          <span style={{ fontFamily: 'monospace', fontSize: 11 }}>
            {item.id} · {item.attempt}/{item.max_attempts}
            {item.poison && ' · POISON'}
          </span>
          <button
            onClick={() => removeRetry(item.id)}
            style={{
              background: 'transparent',
              color: t.dim,
              border: `1px solid ${t.border}`,
              borderRadius: 3,
              padding: '2px 6px',
              fontSize: 10,
              cursor: 'pointer',
            }}
          >
            drop
          </button>
        </div>
      ))}
    </div>
  );
}

const row: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '6px 0',
  borderBottom: `1px solid ${t.border}`,
};

const subRow: React.CSSProperties = {
  fontSize: 10,
  color: t.dim,
  paddingLeft: 8,
  marginBottom: 4,
};

const label: React.CSSProperties = {
  color: t.dim,
  textTransform: 'uppercase',
  fontSize: 10,
  letterSpacing: 0.5,
};
