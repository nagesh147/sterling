import { api } from '../utils/api';
import { useKiteTelegramTargets } from '../hooks/useKiteTelegram';
import { useKiteSettings } from '../store/useKiteSettings';
import type { NavItem } from './kite/KiteLayout';

// ── Status dots shown in header (always visible in simple mode) ───────────────
export function SimpleStatusDots() {
  /* Reads the Kite Telegram targets. It used to poll `/api/v1/config/telegram`,
     which was removed with the crypto surface — so the dot was pinned to "not
     configured" for everyone, on a page that IS reachable (Dashboard renders
     SimpleTerminal whenever appMode is not 'pro'). Telegram now lives entirely
     per-target under `/api/v1/kite/telegram`. */
  const { data: tgTargets } = useKiteTelegramTargets();

  const tgOk = !!tgTargets?.targets?.some((t) => t.enabled);

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
