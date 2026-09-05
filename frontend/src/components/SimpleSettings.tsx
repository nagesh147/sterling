import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useExchanges, useUpdateExchange } from '../hooks/useExchanges';
import { api } from '../utils/api';
import { useDailyLossConfig, useUpdateDailyLossConfig } from '../hooks/useRiskConfig';
import { FontPicker } from './FontPicker';
import { useKiteSettings } from '../store/useKiteSettings';
import type { NavItem } from './kite/KiteLayout';

interface TelegramConfig {
  bot_token_set: boolean;
  bot_token_hint: string;
  chat_id: string;
  enabled: boolean;
  reachable: boolean;
}

// ── Status light ──────────────────────────────────────────────────────────────
function StatusLight({ ok, label }: { ok: boolean | null; label: string }) {
  const color = ok === null ? 'var(--t-dim)' : ok ? 'var(--t-blue)' : 'var(--t-red)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%', background: color,
        display: 'inline-block', flexShrink: 0,
      }} />
      <span style={{ fontSize: 9, color, fontWeight: 500, letterSpacing: 0.5 }}>{label}</span>
    </div>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────
function Section({ title, status, children, defaultOpen = true }: { title: string; status?: React.ReactNode; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ marginBottom: 28 }}>
      <div
        onClick={() => setOpen(!open)}
        style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: open ? 14 : 0, cursor: 'pointer', userSelect: 'none' }}
      >
        <span style={{ fontSize: 10, fontWeight: 500, letterSpacing: '0.14em', color: 'var(--t-bright)', textTransform: 'uppercase' }}>{title}</span>
        <div style={{ flex: 1, height: 1, background: 'var(--t-border)' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {status}
          <span style={{ fontSize: 10, color: 'var(--t-dim)', transition: 'transform 0.2s', transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▼</span>
        </div>
      </div>
      {open && children}
    </div>
  );
}

// ── Field ─────────────────────────────────────────────────────────────────────
function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--t-dim)', letterSpacing: '0.08em', marginBottom: 4, textTransform: 'uppercase' }}>{label}</div>
      {children}
      {hint && <div style={{ fontSize: 9, color: 'var(--t-dim)', marginTop: 4, lineHeight: 1.5 }}>{hint}</div>}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box',
  background: 'var(--t-bg)', color: 'var(--t-bright)',
  border: '1px solid var(--t-border)', borderRadius: 6,
  padding: '7px 10px', fontFamily: 'monospace', fontSize: 12, outline: 'none',
  transition: 'border-color 0.15s, background 0.15s',
};

// ── UI Preferences ─────────────────────────────────────────────────────────────

// ── Daily Loss Circuit Breaker ───────────────────────────────────────────────
function DailyLossSection() {
  const { data } = useDailyLossConfig();
  const update = useUpdateDailyLossConfig();
  const [enabled, setEnabled] = React.useState<boolean | null>(null);
  const [soft, setSoft] = React.useState<number | null>(null);
  const [hard, setHard] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (data) {
      if (enabled === null) setEnabled(data.enabled);
      if (soft === null) setSoft(data.soft_warn_usd);
      if (hard === null) setHard(data.hard_halt_usd);
    }
  }, [data]);

  if (!data) return null;

  const handleSave = () => {
    if (enabled !== null && soft !== null && hard !== null) {
      update.mutate({ enabled, soft_warn_usd: soft, hard_halt_usd: hard });
    }
  };

  const isDirty = enabled !== data.enabled || soft !== data.soft_warn_usd || hard !== data.hard_halt_usd;

  const statusLabel = !data.enabled ? 'DISABLED' : (data.level === 'halt' ? 'HALTED' : (data.level === 'warning' ? 'WARNING' : 'CLEAR'));
  const statusColor = !data.enabled ? 'var(--t-dim)' : (data.level === 'halt' ? 'var(--t-red)' : (data.level === 'warning' ? 'var(--t-amber)' : 'var(--t-green)'));

  return (
    <Section title="DAILY LOSS LIMIT" status={<span style={{ fontSize: 9, color: statusColor, fontWeight: 500 }}>{statusLabel}</span>}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ fontSize: 10, color: 'var(--t-dim)', letterSpacing: '0.06em' }}>CIRCUIT BREAKER</span>
        <button
          onClick={() => setEnabled(!enabled)}
          style={{
            background: enabled ? 'var(--t-green)22' : 'var(--t-bg2)',
            color: enabled ? 'var(--t-green)' : 'var(--t-dim)',
            border: `1px solid ${enabled ? 'var(--t-green)66' : 'var(--t-border)'}`,
            padding: '4px 10px',
            borderRadius: 4,
            fontSize: 10,
            cursor: 'pointer',
            fontWeight: 500,
          }}
        >
          {enabled ? 'ON' : 'OFF'}
        </button>
      </div>

      <Field label="SOFT WARN (USD)" hint="Warning level before hard halt. Expressed as negative USD (e.g. -1000)">
        <input
          type="number"
          step={100}
          value={soft ?? 0}
          onChange={e => setSoft(parseFloat(e.target.value))}
          style={inputStyle}
          disabled={!enabled}
        />
      </Field>
      <Field label="HARD HALT (USD)" hint="Blocks new orders if daily realized PnL drops below this">
        <input
          type="number"
          step={100}
          value={hard ?? 0}
          onChange={e => setHard(parseFloat(e.target.value))}
          style={inputStyle}
          disabled={!enabled}
        />
      </Field>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
        <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>
          Realized Today: <strong style={{ color: data.pnl_usd < 0 ? 'var(--t-red)' : 'var(--t-green)' }}>${data.pnl_usd.toFixed(2)}</strong>
        </span>
        <button
          onClick={handleSave}
          disabled={update.isPending || !isDirty}
          style={{
            padding: '6px 12px', borderRadius: 4,
            fontFamily: 'inherit', fontSize: 10, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase',
            cursor: update.isPending || !isDirty ? 'not-allowed' : 'pointer',
            background: isDirty ? 'var(--t-bg2)' : 'transparent',
            color: isDirty ? 'var(--t-bright)' : 'var(--t-dim)',
            border: '1px solid var(--t-border)',
            opacity: update.isPending || !isDirty ? 0.4 : 1,
          }}
        >
          {update.isPending ? 'Saving…' : (isDirty ? 'Save Config' : 'Saved')}
        </button>
      </div>
    </Section>
  );
}

function UiSection() {
  return (
    <Section title="DISPLAY">
      <FontPicker />
    </Section>
  );
}

// ── Status dots shown in header (always visible in simple mode) ───────────────
export function SimpleStatusDots() {
  const { data: tgData }  = useQuery<TelegramConfig>({
    queryKey: ['telegram-config'],
    queryFn: () => api.get<TelegramConfig>('/api/v1/config/telegram'),
    staleTime: 60_000,
  });

  const tgOk    = !!(tgData?.enabled && tgData?.reachable);

  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
      <span style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: 0.5, fontWeight: 500 }} title={tgOk ? 'Telegram connected' : 'Telegram not configured'}>
        <span style={{ color: tgOk ? 'var(--t-blue)' : 'var(--t-dim)', marginRight: 4 }}>●</span>
        TG
      </span>
    </div>
  );
}

// ── Main drawer ───────────────────────────────────────────────────────────────
export function SimpleSettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 2000 }} />
      <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 380, zIndex: 2001, background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', overflowY: 'auto', scrollbarWidth: 'thin', padding: '20px 22px 48px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, paddingBottom: 16, borderBottom: '1px solid var(--t-border)' }}>
          <span style={{ fontSize: 10, fontWeight: 500, color: 'var(--t-bright)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>SETTINGS</span>
          <button onClick={onClose} style={{ background: 'var(--t-bg2)', border: '1px solid var(--t-border)', borderRadius: 4, color: 'var(--t-dim)', cursor: 'pointer', fontSize: 12, padding: '3px 8px', lineHeight: 1 }}>✕</button>
        </div>

        {/* ── UI preferences ── */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--t-bright)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>DISPLAY</span>
          </div>
          <DefaultPageLoadSectionPicker />
        </div>

      </div>
    </>
  );
}

function DefaultPageLoadSectionPicker() {
  const defaultSection = useKiteSettings((s) => s.defaultSection || 'dashboard');
  const setDefaultSection = useKiteSettings((s) => s.setDefaultSection);

  const options: Array<{ value: NavItem; label: string }> = [
    { value: 'dashboard', label: 'Dashboard' },
    { value: 'positions', label: 'Positions' },
    { value: 'orders', label: 'Orders' },
    { value: 'holdings', label: 'Holdings' },
    { value: 'astro', label: 'Astrology' },
    { value: 'pcr', label: 'PCR' },
    { value: 'openingLeaders', label: 'Opening Leaders' },
    { value: 'adaptiveEdge', label: 'Adaptive Edge' },
    { value: 'backtest', label: 'Backtest' },
    { value: 'data', label: 'Data' },
    { value: 'connect', label: 'Connect' },
    { value: 'more', label: 'More' },
    { value: 'help', label: 'Help' },
  ];

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 11, color: 'var(--t-dim)', marginBottom: 6 }}>Default Section on Load:</div>
      <select
        value={defaultSection}
        onChange={(e) => setDefaultSection(e.target.value as NavItem)}
        style={{
          width: '100%',
          padding: '6px 10px',
          background: 'var(--t-bg2)',
          border: '1px solid var(--t-border)',
          borderRadius: 4,
          color: 'var(--t-bright)',
          fontSize: 11,
          fontFamily: 'inherit',
          cursor: 'pointer',
        }}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

