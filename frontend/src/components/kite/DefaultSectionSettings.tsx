import React from 'react';
import { useKiteSettings } from '../../store/useKiteSettings';
import type { NavItem } from './KiteLayout';
import { SettingsDraftBar } from './config/ConfigPrimitives';
import { useUnsavedDraftGuard } from './config/unsavedDraftGuard';

const OPTIONS: Array<{ value: NavItem; label: string; desc: string }> = [
  { value: 'dashboard', label: 'Dashboard', desc: 'Main trading overview & analytics' },
  { value: 'positions', label: 'Positions', desc: 'Live open positions & PnL' },
  { value: 'orders', label: 'Orders', desc: 'Open, executed, and pending orders' },
  { value: 'holdings', label: 'Holdings', desc: 'Long-term portfolio & equity holdings' },
  { value: 'astro', label: 'Astrology', desc: 'Financial astrology & planetary cycles' },
  { value: 'pcr', label: 'PCR', desc: 'Put-Call Ratio analysis' },
  { value: 'adaptiveEdge', label: 'Adaptive Edge', desc: 'Adaptive Edge score & structure' },
  { value: 'backtest', label: 'Backtest', desc: 'Historical candle & strategy backtest' },
  { value: 'data', label: 'Data', desc: 'Offline data lake & downloads' },
  { value: 'connect', label: 'Connect', desc: 'Kite & TrueData credentials & settings' },
  { value: 'more', label: 'More', desc: 'Bids, funds, alerts & tools' },
  { value: 'help', label: 'Help', desc: 'Documentation & system guides' },
];

export function DefaultSectionSettings() {
  const defaultSection = useKiteSettings((s) => s.defaultSection || 'dashboard');
  const setDefaultSection = useKiteSettings((s) => s.setDefaultSection);

  const [draft, setDraft] = React.useState<NavItem | null>(null);
  const [resetConfirm, setResetConfirm] = React.useState(false);

  const current = draft ?? defaultSection;
  const dirty = draft !== null && draft !== defaultSection;

  useUnsavedDraftGuard('experience', dirty);

  const handleApply = () => {
    if (draft) {
      setDefaultSection(draft);
      setDraft(null);
    }
  };

  const handleDiscard = () => {
    setDraft(null);
  };

  const handleReset = () => {
    if (!resetConfirm) {
      setResetConfirm(true);
      return;
    }
    setResetConfirm(false);
    setDefaultSection('dashboard');
    setDraft(null);
  };

  return (
    <>
      <SettingsDraftBar
        dirty={dirty}
        onApply={handleApply}
        onDiscard={handleDiscard}
        onReset={handleReset}
        resetConfirm={resetConfirm}
      />

      <section style={{ margin: '0 0 16px', padding: 18, background: 'var(--k-bg)', border: '1px solid var(--k-border)', borderRadius: 9, boxShadow: '0 1px 2px rgba(0,0,0,.025)' }}>
        <div style={{ color: 'var(--k-ink-5)', fontSize: 10.5, letterSpacing: .75, marginBottom: 6, fontWeight: 750 }}>
          DEFAULT PAGE LOAD SECTION
        </div>
        <div style={{ color: 'var(--k-ink-5)', fontSize: 11.5, lineHeight: 1.5, marginBottom: 14 }}>
          Select which section opens by default when loading the app.
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(176px, 1fr))', gap: 8 }}>
          {OPTIONS.map((option) => {
            const selected = option.value === current;
            return (
              <label
                key={option.value}
                style={{
                  minHeight: 54,
                  padding: '8px 10px',
                  display: 'grid',
                  gridTemplateColumns: 'minmax(0, 1fr) 16px',
                  alignItems: 'center',
                  gap: 10,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  borderRadius: 7,
                  border: `1px solid ${selected ? 'var(--k-border-brand)' : 'var(--k-border)'}`,
                  background: selected ? 'var(--k-surface-warm)' : 'var(--k-bg)',
                  color: 'var(--k-text)',
                }}
              >
                <span style={{ minWidth: 0 }}>
                  <span style={{ display: 'block', fontSize: 12, fontWeight: selected ? 700 : 600 }}>{option.label}</span>
                  <span style={{ display: 'block', marginTop: 2, fontSize: 9.5, color: 'var(--k-ink-6)', lineHeight: 1.25 }}>{option.desc}</span>
                </span>
                <input
                  type="radio"
                  name="default-section"
                  checked={selected}
                  onChange={() => setDraft(option.value)}
                  style={{ width: 15, height: 15, margin: 0, accentColor: 'var(--k-brand)' }}
                />
              </label>
            );
          })}
        </div>
      </section>
    </>
  );
}

export default DefaultSectionSettings;
