import React, { useState } from 'react';
import { downloadCSV } from '../hooks/useDownload';

const S: Record<string, React.CSSProperties> = {
  row: { display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginTop: 10 },
  btn: {
    background: '#1a1a2a', color: '#88aaff', border: '1px solid #334',
    padding: '6px 14px', borderRadius: 3, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 11, letterSpacing: 1,
  },
  btnRed: {
    background: '#2a1a1a', color: '#cc6644', border: '1px solid #cc664433',
    padding: '6px 14px', borderRadius: 3, cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 11, letterSpacing: 1,
  },
  label: { color: '#555', fontSize: 10, letterSpacing: 1 },
  confirm: {
    background: '#1f0d0d', border: '1px solid #cc4444', borderRadius: 4,
    padding: '8px 12px', fontSize: 11, color: '#cc8888', display: 'flex',
    gap: 8, alignItems: 'center', marginTop: 6,
  },
};

const BASE = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';

async function exportJSON() {
  const resp = await fetch(`${BASE}/api/v1/session/export`);
  if (!resp.ok) throw new Error(resp.statusText);
  const data = await resp.json();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `sterling_session_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function resetSession() {
  await fetch(`${BASE}/api/v1/session/reset`, { method: 'DELETE' });
}

export function SessionExport() {
  const [showConfirm, setShowConfirm] = useState(false);
  const [resetting, setResetting] = useState(false);

  const handleReset = async () => {
    setResetting(true);
    await resetSession().catch(() => {});
    setShowConfirm(false);
    setResetting(false);
    window.location.reload();
  };

  return (
    <div>
      <div style={S.label}>SESSION DATA</div>
      <div style={S.row}>
        <button style={S.btn} onClick={() => exportJSON().catch(console.error)}>
          ↓ EXPORT SESSION JSON
        </button>
        <button style={S.btn}
          onClick={() => downloadCSV('/api/v1/positions/export', 'sterling_positions.csv')}>
          ↓ POSITIONS CSV
        </button>
        <button style={S.btn}
          onClick={() => downloadCSV('/api/v1/account/fills/export', 'sterling_fills.csv')}>
          ↓ FILLS CSV
        </button>
        <button style={S.btnRed} onClick={() => setShowConfirm(true)}>
          ⚠ RESET SESSION
        </button>
      </div>
      {showConfirm && (
        <div style={S.confirm}>
          <span>Clears eval history, arrows, alerts, P&L history. Positions in DB preserved.</span>
          <button style={S.btnRed} onClick={handleReset} disabled={resetting}>
            {resetting ? 'RESETTING…' : 'CONFIRM'}
          </button>
          <button style={{ ...S.btn, fontSize: 10 }} onClick={() => setShowConfirm(false)}>
            CANCEL
          </button>
        </div>
      )}
    </div>
  );
}
