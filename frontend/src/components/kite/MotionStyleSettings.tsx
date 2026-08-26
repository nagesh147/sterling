import React from 'react';
import { useKiteSettings, type LoaderStyle } from '../../store/useKiteSettings';
import { KiteLoader } from './KiteLoader';

const OPTIONS: Array<{ value: LoaderStyle; label: string; desc: string }> = [
  { value: 'ubuntu', label: 'Ubuntu', desc: 'Crisp, fast and direct' },
  { value: 'mac', label: 'Mac', desc: 'Soft spring and glass' },
  { value: 'material', label: 'Material', desc: 'Clean scale and ripple' },
  { value: 'windows', label: 'Windows', desc: 'Precise fluent motion' },
  { value: 'gnome', label: 'GNOME', desc: 'Calm ease and fade' },
  { value: 'kde', label: 'KDE', desc: 'Snappy desktop feedback' },
  { value: 'minimal', label: 'Minimal', desc: 'Almost instant, no flourish' },
];

export function MotionStyleSettings() {
  const style = useKiteSettings((s) => s.loaderStyle);
  const setStyle = useKiteSettings((s) => s.setLoaderStyle);

  return (
    <section style={{ margin: '0 0 16px', padding: 18, background: 'var(--k-bg)', border: '1px solid var(--k-border)', borderRadius: 9, boxShadow: '0 1px 2px rgba(0,0,0,.025)' }}>
      <div style={{ color: 'var(--k-ink-5)', fontSize: 10.5, letterSpacing: .75, marginBottom: 6, fontWeight: 750 }}>
        INTERACTION & LOADER STYLE
      </div>
      <div style={{ color: 'var(--k-ink-5)', fontSize: 11.5, lineHeight: 1.5, marginBottom: 14 }}>
        Controls loaders, startup surfaces, menus, dialogs, buttons and transition timing. Table rows remain stationary for accurate scrolling and pointer targeting.
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(176px, 1fr))', gap: 8 }}>
        {OPTIONS.map((option) => {
          const selected = option.value === style;
          return (
            <label
              key={option.value}
              style={{
                minHeight: 62,
                padding: '8px 10px',
                display: 'grid',
                gridTemplateColumns: '32px minmax(0, 1fr) 16px',
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
              <span style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <KiteLoader size={24} styleOverride={option.value} />
              </span>
              <span style={{ minWidth: 0 }}>
                <span style={{ display: 'block', fontSize: 12, fontWeight: selected ? 700 : 600 }}>{option.label}</span>
                <span style={{ display: 'block', marginTop: 2, fontSize: 9.5, color: 'var(--k-ink-6)', lineHeight: 1.25 }}>{option.desc}</span>
              </span>
              <input type="radio" name="motion-style" checked={selected} onChange={() => setStyle(option.value)} style={{ width: 15, height: 15, margin: 0, accentColor: 'var(--k-brand)' }} />
            </label>
          );
        })}
      </div>
    </section>
  );
}

export default MotionStyleSettings;
