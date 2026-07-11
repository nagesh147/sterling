import React, { useState } from 'react';
import { useKiteGtts } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';
import { CreateGttModal } from './CreateGttModal';
import { GttOptionsModal } from './GttOptionsModal';

const S: Record<string, React.CSSProperties> = {
  emptyContainer: { display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 100 },
  emptyTitle: { fontSize: 14, color: '#9b9b9b', marginBottom: 24, textAlign: 'center', lineHeight: '20px', maxWidth: 350 },
  primaryBtn: { background: '#387ed1', color: 'white', padding: '10px 20px', borderRadius: 3, border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 500 },
  th: { textAlign: 'left', color: '#9b9b9b', fontSize: 12, fontWeight: 400, padding: '12px 16px', borderBottom: '1px solid #f1f1f1' },
  td: { padding: '12px 16px', fontSize: 13, color: '#444', borderBottom: '1px solid #f1f1f1' },
};

const GTT_STATUS_COLOR: Record<string, { fg: string; bg: string }> = {
  active: { fg: '#4caf50', bg: 'rgba(76, 175, 80, 0.1)' },
  triggered: { fg: '#387ed1', bg: 'rgba(56, 126, 209, 0.1)' },
  expired: { fg: '#9b9b9b', bg: 'rgba(155, 155, 155, 0.1)' },
  cancelled: { fg: '#df514c', bg: 'rgba(223, 81, 76, 0.1)' },
  deleted: { fg: '#df514c', bg: 'rgba(223, 81, 76, 0.1)' },
  rejected: { fg: '#df514c', bg: 'rgba(223, 81, 76, 0.1)' },
};
function gttStatusStyle(status: string): React.CSSProperties {
  const c = GTT_STATUS_COLOR[(status || '').toLowerCase()] ?? { fg: '#9b9b9b', bg: 'rgba(155, 155, 155, 0.1)' };
  return { padding: '2px 6px', background: c.bg, color: c.fg, borderRadius: 3, fontSize: 11 };
}

export function GttPane() {
  const { data: gtts } = useKiteGtts(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [optionsGtt, setOptionsGtt] = useState<any | null>(null);

  return (
    <>
      {(!gtts || gtts.length === 0) ? (
        <div style={S.emptyContainer}>
          <div style={{ marginBottom: 24 }}>
            <svg width="120" height="84" viewBox="0 0 120 70" fill="none">
              <circle cx="30" cy="30" r="20" fill="#f8f8f8" />
              <circle cx="30" cy="30" r="15" fill="#fff" stroke="#dfe1e4" strokeWidth="2" />
              <path d="M30 20v10l5 5" stroke="#dfe1e4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <rect x="50" y="25" width="40" height="6" rx="2" fill="#ffb74d" />
              <rect x="40" y="35" width="50" height="6" rx="2" fill="#bbdefb" />
              <text x="50" y="55" fill="#387ed1" fontSize="22" fontWeight="bold" fontStyle="italic" letterSpacing="1">gtt</text>
              <circle cx="15" cy="45" r="2" fill="#387ed1" />
              <circle cx="20" cy="50" r="1.5" fill="#387ed1" />
              <circle cx="10" cy="50" r="1" fill="#387ed1" />
            </svg>
          </div>
          <div style={S.emptyTitle}>
            You have not created any triggers. <a href="#" style={{ color: '#387ed1', textDecoration: 'none' }}>Learn more</a> about setting automatic stoploss and target orders for your holdings.
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
                    <span style={{ cursor: 'pointer', color: '#387ed1', marginRight: 12 }} onClick={() => setOptionsGtt(g)}>Options</span>
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
