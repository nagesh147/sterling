import React from 'react';
import { useKiteGtts } from '../../hooks/useKite';

const S: Record<string, React.CSSProperties> = {
  emptyContainer: { display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 100 },
  emptyTitle: { fontSize: 14, color: '#9b9b9b', marginBottom: 24, textAlign: 'center', lineHeight: '20px', maxWidth: 350 },
  primaryBtn: { background: '#387ed1', color: 'white', padding: '10px 20px', borderRadius: 3, border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 500 },
  th: { textAlign: 'left', color: '#9b9b9b', fontSize: 12, fontWeight: 400, padding: '12px 16px', borderBottom: '1px solid #f1f1f1' },
  td: { padding: '12px 16px', fontSize: 13, color: '#444', borderBottom: '1px solid #f1f1f1' },
};

export function GttPane() {
  const { data: gtts } = useKiteGtts(true);

  if (!gtts || gtts.length === 0) {
    return (
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
        <button style={S.primaryBtn}>Create new GTT</button>
      </div>
    );
  }

  return (
    <div style={{ padding: '0 16px' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>
          <th style={S.th}>ID</th><th style={S.th}>Symbol</th><th style={S.th}>Type</th><th style={S.th}>Status</th><th style={S.th} />
        </tr></thead>
        <tbody>
          {gtts.map((g: any) => (
            <tr key={g.id}>
              <td style={S.td}>{g.id}</td>
              <td style={S.td}>{g.condition?.tradingsymbol ?? '—'}</td>
              <td style={S.td}>{g.type}</td>
              <td style={{ ...S.td, color: '#9b9b9b' }}>{g.status}</td>
              <td style={{ ...S.td, textAlign: 'right' }}>
                <span style={{ cursor: 'pointer', color: '#387ed1', marginRight: 12 }}>Options</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
