import React from 'react';
import { k } from '../../styles/kiteUI';
import { useKiteSettings } from '../../store/useKiteSettings';

const TOGGLES: Array<{ key: 'showHoldings' | 'showNotes' | 'showGroupColors' | 'showExchange' | 'showLeg'; label: string }> = [
  { key: 'showHoldings', label: 'Show holdings in watchlist' },
  { key: 'showNotes', label: 'Show notes' },
  { key: 'showGroupColors', label: 'Show group colours' },
  { key: 'showExchange', label: 'Show exchange badge' },
  { key: 'showLeg', label: 'Show leg labels' },
];

/**
 * Surfaces the existing useKiteSettings display-preference store (previously
 * only used internally by the watchlist) as its own popover, reached from
 * Positions/Holdings' "Settings" link — no new state, just a new UI on top
 * of state that already existed.
 */
export function KiteSettingsPopover({ onClose }: { onClose: () => void }) {
  const settings = useKiteSettings();
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 60, right: 40, width: 300, maxWidth: '92vw', background: '#fff', borderRadius: 6, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily, padding: '16px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 500, color: '#444' }}>Display settings</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 16, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        {TOGGLES.map(({ key, label }) => (
          <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: '#444', cursor: 'pointer', padding: '6px 0' }}>
            <input type="checkbox" checked={settings[key]} onChange={() => settings.toggleShow(key)} style={{ accentColor: k.blue, width: 14, height: 14 }} />
            {label}
          </label>
        ))}
      </div>
    </>
  );
}
