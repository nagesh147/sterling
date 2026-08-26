import React, { useState, useEffect } from 'react';
import { useKiteGtts } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';
import { CreateGttModal } from './CreateGttModal';
import { GttOptionsModal } from './GttOptionsModal';

const S: Record<string, React.CSSProperties> = {
  emptyContainer: { display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 100 },
  emptyTitle: { fontSize: 14, color: 'var(--k-dim)', marginBottom: 24, textAlign: 'center', lineHeight: '20px', maxWidth: 350 },
  primaryBtn: { background: 'var(--k-blue-kite)', color: 'var(--k-on-accent)', padding: '10px 20px', borderRadius: 3, border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 500 },
  th: { textAlign: 'left', color: 'var(--k-dim)', fontSize: 12, fontWeight: 400, padding: '12px 16px', borderBottom: '1px solid var(--k-surface-hover)' },
  td: { padding: '12px 16px', fontSize: 13, color: 'var(--k-text)', borderBottom: '1px solid var(--k-surface-hover)' },
};

const GTT_STATUS_COLOR: Record<string, { fg: string; bg: string }> = {
  active: { fg: 'var(--k-green)', bg: 'rgba(76, 175, 80, 0.1)' },
  triggered: { fg: 'var(--k-blue-kite)', bg: 'rgba(56, 126, 209, 0.1)' },
  expired: { fg: 'var(--k-dim)', bg: 'rgba(155, 155, 155, 0.1)' },
  cancelled: { fg: 'var(--k-red)', bg: 'rgba(223, 81, 76, 0.1)' },
  deleted: { fg: 'var(--k-red)', bg: 'rgba(223, 81, 76, 0.1)' },
  rejected: { fg: 'var(--k-red)', bg: 'rgba(223, 81, 76, 0.1)' },
};
function gttStatusStyle(status: string): React.CSSProperties {
  const c = GTT_STATUS_COLOR[(status || '').toLowerCase()] ?? { fg: 'var(--k-dim)', bg: 'rgba(155, 155, 155, 0.1)' };
  return { padding: '2px 6px', background: c.bg, color: c.fg, borderRadius: 3, fontSize: 11 };
}

const GTT_MODIFIABLE_STATUSES = new Set(['active']);

export function GttPane() {
  const { data: gtts } = useKiteGtts(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [optionsGtt, setOptionsGtt] = useState<any | null>(null);

  useEffect(() => {
    if (!optionsGtt || !gtts) return;
    const current = gtts.find((g: any) => g.id === optionsGtt.id);
    if (!current || !GTT_MODIFIABLE_STATUSES.has((current.status || '').toLowerCase())) {
      setOptionsGtt(null);
    }
  }, [gtts, optionsGtt]);

  return (
    <>
      {(!gtts || gtts.length === 0) ? (
        <div style={S.emptyContainer}>
          <div style={{ marginBottom: 24 }}>
            <svg width="120" height="84" viewBox="0 0 120 70" fill="none">
              <circle cx="30" cy="30" r="20" fill="#f8f8f8" />
              <circle cx="30" cy="30" r="15" fill="var(--k-bg)" stroke="var(--k-border-strong)" strokeWidth="2" />
              <path d="M30 20v10l5 5" stroke="var(--k-border-strong)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <rect x="50" y="25" width="40" height="6" rx="2" fill="#ffb74d" />
              <rect x="40" y="35" width="50" height="6" rx="2" fill="#bbdefb" />
              <text x="50" y="55" fill="var(--k-blue-kite)" fontSize="22" fontWeight="bold" fontStyle="italic" letterSpacing="1">gtt</text>
              <circle cx="15" cy="45" r="2" fill="var(--k-blue-kite)" />
              <circle cx="20" cy="50" r="1.5" fill="var(--k-blue-kite)" />
              <circle cx="10" cy="50" r="1" fill="var(--k-blue-kite)" />
            </svg>
          </div>
          <div style={S.emptyTitle}>
            You have not created any triggers. <a href="#" style={{ color: 'var(--k-blue-kite)', textDecoration: 'none' }}>Learn more</a> about setting automatic stoploss and target orders for your holdings.
          </div>
          <button style={S.primaryBtn} onClick={() => setCreateOpen(true)}>Create new GTT</button>
        </div>
      ) : (
        <div style={{ padding: '0 16px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>ID</th><th style={S.th}>Symbol</th><th style={S.th}>Type</th><th style={S.th}>Status</th><th style={S.th} />
            </tr></thead>
            <tbody>
              {gtts.map((g: any) => (
                <tr key={g.id}>
                  <td style={S.td}>{g.id}</td>
                  <td style={S.td}><InstrumentLabel symbol={g.condition?.tradingsymbol ?? ''} fallback="—" /></td>
                  <td style={S.td}>{g.type}</td>
                  <td style={S.td}><span style={gttStatusStyle(g.status)}>{g.status}</span></td>
                  <td style={{ ...S.td, textAlign: 'right' }}>
                    <span style={{ cursor: 'pointer', color: 'var(--k-blue-kite)', marginRight: 12 }} onClick={() => setOptionsGtt(g)}>Options</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {createOpen && <CreateGttModal onClose={() => setCreateOpen(false)} />}
      {optionsGtt && <GttOptionsModal gtt={optionsGtt} onClose={() => setOptionsGtt(null)} />}
    </>
  );
}
