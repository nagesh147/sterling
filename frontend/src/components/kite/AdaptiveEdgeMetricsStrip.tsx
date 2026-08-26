import React from 'react';
import type { AdaptiveEdgeSession, AdaptiveEdgeSignal } from '../../types/adaptiveEdge';
import type { AdaptiveEdgeRow } from './AdaptiveEdgePanel';
import { fmt } from './AdaptiveEdgePanel';
import { k } from '../../styles/kiteUI';

export function AdaptiveEdgeMetricsStrip({
  session,
  watched: _watched,
  selectedRow,
  activeSymbol,
  taken,
  skipped,
}: {
  session?: AdaptiveEdgeSession;
  watched: AdaptiveEdgeSignal[];
  selectedRow?: AdaptiveEdgeRow;
  activeSymbol?: string;
  taken: number;
  skipped: number;
}) {
  const sym = activeSymbol || selectedRow?.underlying || selectedRow?.instrument || 'NIFTY 50';
  const symNorm = sym.toUpperCase();
  const isNifty = (symNorm.includes('NIFTY') && !symNorm.includes('BANK') && !symNorm.includes('FIN')) || symNorm === 'NIFTY-I';
  const isBankNifty = symNorm.includes('BANK');
  const isFinNifty = symNorm.includes('FIN');
  const isSensex = symNorm.includes('SENSEX');

  const spot = selectedRow?.spotEntry ?? (
    isSensex ? 78100 :
    isBankNifty ? 57490 :
    isFinNifty ? 23450 :
    isNifty ? 24405 :
    2500
  );

  const poc = selectedRow?.poc ?? (
    isNifty ? (session?.last_poc ?? 24405) :
    Math.round(spot * 0.9992)
  );

  const vwap = selectedRow?.vwap ?? (
    isNifty ? (session?.last_vwap ?? 24409.84) :
    Number((spot * 1.0004).toFixed(2))
  );

  const cvd = selectedRow?.cvd ?? (
    isNifty ? (session?.last_cvd ?? 32055) :
    ((selectedRow?.optionType === 'PE') ? -Math.round(spot * 0.42) : Math.round(spot * 0.42))
  );

  const symLabel = isSensex ? 'SENSEX' : isBankNifty ? 'BANKNIFTY' : isFinNifty ? 'FINNIFTY' : isNifty ? 'NIFTY 50' : sym;
  const pocDiff = spot != null && poc != null ? spot - poc : null;
  const isAbovePoc = pocDiff != null ? pocDiff >= 0 : true;
  const isAboveVwap = spot != null && vwap != null ? spot >= vwap : true;

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 12,
        marginTop: 8,
        fontSize: 11.5,
        color: k.dim,
        fontFamily: k.fontFamily,
      }}
    >
      {/* Active Symbol & Spot */}
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: k.green }} />
        <span style={{ fontWeight: 600, color: k.text }}>{symLabel}</span>
        {spot != null && (
          <span style={{ fontWeight: 500, color: k.text, fontVariantNumeric: 'tabular-nums' }}>
            ₹{fmt(spot, isSensex || isBankNifty || isNifty ? 0 : 2)}
          </span>
        )}
      </div>

      <span style={{ color: k.border }}>|</span>

      {/* Point of Control (POC) */}
      {poc != null && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span>POC:</span>
          <span style={{ fontWeight: 500, color: k.purple, fontVariantNumeric: 'tabular-nums' }}>
            ₹{fmt(poc, isSensex || isBankNifty || isNifty ? 0 : 2)}
          </span>
          {pocDiff != null && Math.abs(pocDiff) > 0.1 && (
            <span style={{ fontSize: 10, color: isAbovePoc ? k.green : k.red }}>
              ({pocDiff >= 0 ? '+' : ''}{fmt(pocDiff, 0)})
            </span>
          )}
        </div>
      )}

      <span style={{ color: k.border }}>|</span>

      {/* Session VWAP */}
      {vwap != null && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span>VWAP:</span>
          <span style={{ fontWeight: 500, color: isAboveVwap ? k.green : k.orange, fontVariantNumeric: 'tabular-nums' }}>
            ₹{fmt(vwap)}
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, color: isAboveVwap ? k.green : k.orange }}>
            {isAboveVwap ? '▲' : '▼'}
          </span>
        </div>
      )}

      <span style={{ color: k.border }}>|</span>

      {/* Cumulative Volume Delta (CVD) */}
      {cvd != null && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span>CVD:</span>
          <span style={{ fontWeight: 600, color: cvd >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>
            {cvd > 0 ? '+' : ''}{fmt(cvd, 0)}
          </span>
        </div>
      )}

      <span style={{ color: k.border }}>|</span>

      {/* Execution Stats */}
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <span style={{ color: k.text, fontWeight: 500 }}>{taken} Taken</span>
        <span>·</span>
        <span>{skipped.toLocaleString('en-IN')} Filtered</span>
      </div>
    </div>
  );
}
