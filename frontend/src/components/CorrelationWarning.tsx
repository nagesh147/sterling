import React from 'react';
import type { PaperPosition } from '../types';

interface CorrelationWarningProps {
  newUnderlying: string;
  newDirection: 'long' | 'short';
  openPositions: PaperPosition[];
  onProceed: () => void;
  onCancel: () => void;
}

const CRYPTO_ASSETS = new Set(['BTC', 'ETH', 'SOL', 'BNB', 'AVAX', 'MATIC', 'DOT', 'LINK']);

function assetClass(sym: string): string {
  if (CRYPTO_ASSETS.has(sym)) return 'crypto';
  return 'other';
}

export function CorrelationWarning({
  newUnderlying, newDirection, openPositions, onProceed, onCancel,
}: CorrelationWarningProps) {
  const newClass = assetClass(newUnderlying);

  const sameDirectionSameClass = openPositions.filter((p) => {
    const dir = p.sized_trade?.structure?.direction?.valueOf() ?? '';
    const matches = dir === newDirection;
    const sameClass = assetClass(p.underlying) === newClass;
    const isOpen = p.status === 'open' || p.status === 'partially_closed';
    return isOpen && matches && sameClass;
  });

  if (sameDirectionSameClass.length < 2) return null;

  const names = sameDirectionSameClass.map((p) => p.underlying).join(', ');

  return (
    <div style={{
      background: '#1a1400', border: '1px solid #f0c04055',
      borderRadius: 4, padding: '12px 16px', marginBottom: 12,
    }}>
      <div style={{ color: '#f0c040', fontWeight: 700, fontSize: 12, marginBottom: 6 }}>
        Correlation Warning
      </div>
      <div style={{ color: '#888', fontSize: 11, marginBottom: 12 }}>
        Adding {newUnderlying} {newDirection} — you already have {sameDirectionSameClass.length}{' '}
        {newClass} {newDirection}s open ({names}). High correlation risk.
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={onCancel}
          style={{
            background: '#1a1a1a', color: '#555', border: '1px solid #333',
            borderRadius: 3, padding: '4px 14px', cursor: 'pointer',
            fontFamily: 'inherit', fontSize: 11,
          }}
        >
          Cancel
        </button>
        <button
          onClick={onProceed}
          style={{
            background: '#2a1a00', color: '#f0c040', border: '1px solid #f0c040',
            borderRadius: 3, padding: '4px 14px', cursor: 'pointer',
            fontFamily: 'inherit', fontSize: 11,
          }}
        >
          Proceed Anyway
        </button>
      </div>
    </div>
  );
}
