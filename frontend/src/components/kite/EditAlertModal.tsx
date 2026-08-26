import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useModifyKiteAlert, useDeleteKiteAlerts } from '../../hooks/useKite';
import type { KiteAlert } from '../../types/kite';

export function EditAlertModal({ alert, onClose }: { alert: KiteAlert; onClose: () => void }) {
  const modify = useModifyKiteAlert();
  const del = useDeleteKiteAlerts();
  const [threshold, setThreshold] = useState(alert.rhs_constant ?? 0);
  const [error, setError] = useState<string | null>(null);
  const busy = modify.isPending || del.isPending;

  const save = () => {
    setError(null);
    if (!(threshold > 0)) { setError('Enter a threshold value'); return; }
    modify.mutate({ uuid: alert.uuid, rhs_constant: threshold }, { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Modify failed') });
  };

  const remove = () => {
    setError(null);
    if (!window.confirm(`Delete the "${alert.name}" alert?`)) return;
    del.mutate([alert.uuid], { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Delete failed') });
  };

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 100, left: '50%', transform: 'translateX(-50%)', width: 380, background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${k.border}` }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 500, color: 'var(--k-text)' }}>{alert.name}</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: 'var(--k-dim)', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <label style={{ fontSize: 12, color: 'var(--k-dim)' }}>Threshold
            <input
              type="number"
              step={0.05}
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              onKeyDown={(e) => { if (e.key === 'Enter') save(); }}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }}
            />
          </label>
          {error && <div style={{ color: k.red, fontSize: 12 }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '14px 18px', borderTop: `1px solid ${k.border}` }}>
          <button onClick={remove} disabled={busy} style={{ background: 'var(--k-bg)', color: k.red, border: `1px solid ${k.red}`, borderRadius: 3, padding: '9px 16px', fontSize: 13, cursor: busy ? 'not-allowed' : 'pointer' }}>Delete</button>
          <button onClick={save} disabled={busy} style={{ flex: 1, background: k.blue, color: 'var(--k-bg)', border: 'none', borderRadius: 3, padding: '9px', fontSize: 13, fontWeight: 600, cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.6 : 1 }}>
            {modify.isPending ? '…' : 'Save changes'}
          </button>
        </div>
      </div>
    </>
  );
}
