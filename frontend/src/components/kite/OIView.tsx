import React, { useState, useEffect, useMemo } from 'react';
import { k } from '../../styles/kiteUI';
import { useKiteOptionChain } from '../../hooks/useKiteOptionChain';

// ─── OI Change / Open Interest tabs ───────────────────────────────────────────
// Sensibull-style horizontal-bar view of open interest by strike, Call vs Put.
//   mode="total"  → total OI per strike (the "Open Interest" tab)
//   mode="change" → change in OI per strike (the "OI Change" tab)
//
// Data: the same live per-symbol chain the Option-chain tab uses (polls ~15s).
// Total OI is a real field (leg.oi). Kite's quote has NO change-in-OI field and
// there is no intraday OI-history API, so ΔOI is derived on the client against a
// DAY BASELINE: the first OI snapshot observed today per (underlying, expiry),
// cached in localStorage and diffed on every refetch. Honestly labelled as
// "since first snapshot today" - not a true since-previous-close figure.

type Mode = 'total' | 'change';
type OiRow = {
  strike: number;
  isAtm: boolean;
  ce: { oi: number; chg: number };
  pe: { oi: number; chg: number };
};
type Baseline = { at: number; oi: Record<string, { ce: number; pe: number }> };

// IST calendar date (YYYY-MM-DD) - the baseline resets each trading day.
function istDateKey(): string {
  try {
    return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
  } catch {
    return new Date().toISOString().slice(0, 10);
  }
}
function istTime(ms: number): string {
  try {
    return new Date(ms).toLocaleTimeString('en-IN', {
      timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: false,
    });
  } catch {
    return '';
  }
}

// ── Placeholder (dev / no-session) chain, NIFTY-shaped, so the tab is not blank.
// Clearly labelled in the header when live data is absent; never mixed with live.
function buildPlaceholder(): { spot: number; atm: number; rows: OiRow[] } {
  const spot = 23949.35, step = 50;
  const atm = Math.round(spot / step) * step;
  const start = atm - 11 * step;
  const rows: OiRow[] = Array.from({ length: 23 }).map((_, i) => {
    const strike = start + i * step;
    const dist = Math.abs(strike - spot);
    const base = Math.max(2, 55 - dist / 40);
    return {
      strike,
      isAtm: strike === atm,
      ce: { oi: Number((base * (strike >= spot ? 1.25 : 0.7) + Math.random() * 8).toFixed(2)), chg: Number(((Math.random() - 0.4) * 24).toFixed(2)) },
      pe: { oi: Number((base * (strike <= spot ? 1.25 : 0.7) + Math.random() * 8).toFixed(2)), chg: Number(((Math.random() - 0.4) * 24).toFixed(2)) },
    };
  });
  return { spot, atm, rows };
}
const PLACEHOLDER = buildPlaceholder();

export function OIView({ symbol, mode }: { symbol: string; mode: Mode }) {
  const [expiry, setExpiry] = useState(0);
  const { data: live } = useKiteOptionChain(symbol);
  const [baseline, setBaseline] = useState<Baseline | null>(null);

  const name = symbol.split(':')[1] || symbol;
  const liveExpiries = live?.expiries ?? [];
  const isLive = !!(live && liveExpiries.length && live.chain);

  const selIdx = Math.min(expiry, Math.max(0, (isLive ? liveExpiries.length : 1) - 1));
  const expiryDate = isLive ? (liveExpiries[selIdx]?.date ?? '') : 'placeholder';
  const underlying = live?.underlying ?? name;

  // Raw live rows for the selected expiry (oi only; chg filled in after baseline).
  const liveRows = useMemo(() => {
    if (!isLive) return [];
    const raw = live!.chain[expiryDate] ?? [];
    return raw.map((r: any) => ({
      strike: r.strike,
      isAtm: !!r.isAtm,
      ce: { oi: r.call?.oi ?? 0, chg: 0 },
      pe: { oi: r.put?.oi ?? 0, chg: 0 },
    })) as OiRow[];
  }, [isLive, live, expiryDate]);

  // Capture / load the day baseline for the selected (underlying, expiry).
  useEffect(() => {
    if (!isLive || !liveRows.length) { setBaseline(null); return; }
    const key = `kiteOiBaseline:${underlying}:${expiryDate}:${istDateKey()}`;
    let bl: Baseline | null = null;
    try { const raw = localStorage.getItem(key); if (raw) bl = JSON.parse(raw); } catch { /* ignore */ }
    if (!bl || !bl.oi) {
      const oi: Record<string, { ce: number; pe: number }> = {};
      for (const r of liveRows) oi[r.strike] = { ce: r.ce.oi, pe: r.pe.oi };
      bl = { at: Date.now(), oi };
      try { localStorage.setItem(key, JSON.stringify(bl)); } catch { /* ignore */ }
    }
    setBaseline(bl);
  }, [isLive, underlying, expiryDate, liveRows]);

  // Final rows: live rows with ΔOI vs baseline, else the placeholder chain.
  const rows: OiRow[] = useMemo(() => {
    if (!isLive) return PLACEHOLDER.rows;
    if (mode !== 'change' || !baseline) return liveRows;
    return liveRows.map((r) => {
      const b = baseline.oi[r.strike];
      return {
        ...r,
        ce: { ...r.ce, chg: Number((r.ce.oi - (b?.ce ?? r.ce.oi)).toFixed(2)) },
        pe: { ...r.pe, chg: Number((r.pe.oi - (b?.pe ?? r.pe.oi)).toFixed(2)) },
      };
    });
  }, [isLive, mode, baseline, liveRows]);

  const spot = isLive ? live!.spot : PLACEHOLDER.spot;

  // Scale bars by the largest magnitude in view for the active mode.
  const maxVal = useMemo(() => {
    let m = 1;
    for (const r of rows) {
      const cv = mode === 'change' ? Math.abs(r.ce.chg) : r.ce.oi;
      const pv = mode === 'change' ? Math.abs(r.pe.chg) : r.pe.oi;
      m = Math.max(m, cv, pv);
    }
    return m;
  }, [rows, mode]);

  // Footer stats.
  const stats = useMemo(() => {
    let ceOi = 0, peOi = 0, ceChg = 0, peChg = 0;
    for (const r of rows) { ceOi += r.ce.oi; peOi += r.pe.oi; ceChg += r.ce.chg; peChg += r.pe.chg; }
    // Max pain = strike minimising total option-writer payout across the chain.
    let maxPain = '–', bestLoss = Infinity;
    for (const kr of rows) {
      let loss = 0;
      for (const s of rows) {
        loss += s.ce.oi * Math.max(0, kr.strike - s.strike);
        loss += s.pe.oi * Math.max(0, s.strike - kr.strike);
      }
      if (loss < bestLoss) { bestLoss = loss; maxPain = String(kr.strike); }
    }
    return { ceOi, peOi, ceChg, peChg, pcr: ceOi > 0 ? peOi / ceOi : 0, maxPain };
  }, [rows]);

  const expiryPills = isLive
    ? liveExpiries.map((e) => `${e.label} (${e.dte}${e.dte === 1 ? 'd' : 'd'})`)
    : ['23 Jun (4d)', '30 Jun (11d)', '7 Jul (3w)'];

  const CE = 'rgba(223,81,76,'; // red
  const PE = 'rgba(76,175,80,'; // green
  const GRID = '78px 1fr 78px 1fr 78px';
  const isChange = mode === 'change';

  // One diverging bar. Positive change = solid; negative (unwind) = hollow.
  const Bar = ({ pct, side, negative }: { pct: number; side: 'ce' | 'pe'; negative: boolean }) => {
    const rgba = side === 'ce' ? CE : PE;
    return (
      <div style={{ display: 'flex', justifyContent: side === 'ce' ? 'flex-end' : 'flex-start', alignItems: 'center', height: '100%' }}>
        <div style={{
          width: `${Math.max(1.5, pct)}%`, height: 12, borderRadius: 2,
          background: negative ? 'transparent' : rgba + '0.72)',
          border: negative ? `1px solid ${rgba}0.85)` : 'none',
        }} />
      </div>
    );
  };

  const Num = ({ v, signed, side }: { v: number; signed?: boolean; side: 'ce' | 'pe' }) => (
    <span style={{
      fontSize: 11.5, fontVariantNumeric: 'tabular-nums',
      color: signed ? (v > 0 ? k.green : v < 0 ? k.red : k.dim) : k.text,
      textAlign: side === 'ce' ? 'right' : 'left', width: '100%', display: 'block',
    }}>
      {signed && v > 0 ? '+' : ''}{v.toFixed(2)}
    </span>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: k.bg, fontFamily: k.fontFamily }}>
      {/* Header */}
      <div style={{ padding: '12px 16px 4px', display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--k-ink-1)' }}>{name}</span>
        <span style={{ fontSize: 13, fontWeight: 500, color: k.text, fontVariantNumeric: 'tabular-nums' }}>
          {spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--k-ink-1)' }}>
          {isChange ? 'Change in OI' : 'Open Interest'}
        </span>
        {!isLive && <span style={{ fontSize: 10, color: k.amber, border: `1px solid ${k.amber}`, borderRadius: 3, padding: '1px 5px' }}>sample</span>}
      </div>

      {/* Caption + legend */}
      <div style={{ padding: '0 16px 8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <span style={{ fontSize: 11, color: k.dim }}>
          {isChange
            ? (baseline ? `Change since first snapshot today · ${istTime(baseline.at)} IST` : 'Change since first snapshot today (intraday)')
            : 'Total open interest by strike (in lakhs)'}
        </span>
        <div style={{ display: 'flex', gap: 14, alignItems: 'center', fontSize: 11, color: k.dim }}>
          <span style={{ display: 'flex', gap: 5, alignItems: 'center' }}><i style={{ width: 10, height: 10, borderRadius: 2, background: CE + '0.72)' }} /> Call</span>
          <span style={{ display: 'flex', gap: 5, alignItems: 'center' }}><i style={{ width: 10, height: 10, borderRadius: 2, background: PE + '0.72)' }} /> Put</span>
          {isChange && <span style={{ display: 'flex', gap: 5, alignItems: 'center' }}><i style={{ width: 10, height: 10, borderRadius: 2, border: `1px solid ${k.dim}` }} /> unwind</span>}
        </div>
      </div>

      {/* Expiry pills */}
      <div style={{ display: 'flex', gap: 4, padding: '0 16px 8px', flexWrap: 'wrap' }}>
        {expiryPills.map((e, idx) => (
          <span
            key={e + idx}
            onClick={() => setExpiry(idx)}
            style={{
              fontSize: 12, cursor: 'pointer', padding: '4px 10px', borderRadius: 14, whiteSpace: 'nowrap',
              background: selIdx === idx ? '#e7f0fe' : 'transparent',
              color: selIdx === idx ? k.blue : k.text, fontWeight: selIdx === idx ? 500 : 400,
            }}
          >
            {e}
          </span>
        ))}
      </div>

      {/* Column header */}
      <div style={{ display: 'grid', gridTemplateColumns: GRID, padding: '7px 16px', borderTop: `1px solid ${k.border}`, borderBottom: `1px solid ${k.border}`, fontSize: 11, color: k.dim, background: k.bg }}>
        <div style={{ textAlign: 'right' }}>Call {isChange ? 'Δ' : ''}</div>
        <div />
        <div style={{ textAlign: 'center' }}>Strike</div>
        <div />
        <div style={{ textAlign: 'left' }}>Put {isChange ? 'Δ' : ''}</div>
      </div>

      {/* Rows */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {rows.length === 0 && (
          <div style={{ padding: 32, textAlign: 'center', color: k.dim, fontSize: 13 }}>
            No option chain available. Connect a Kite account with an active session to load live data.
          </div>
        )}
        {rows.map((r) => {
          const ceV = isChange ? r.ce.chg : r.ce.oi;
          const peV = isChange ? r.pe.chg : r.pe.oi;
          const cePct = (Math.abs(ceV) / maxVal) * 100;
          const pePct = (Math.abs(peV) / maxVal) * 100;
          return (
            <div key={r.strike} style={{ display: 'grid', gridTemplateColumns: GRID, alignItems: 'center', minHeight: 30, padding: '0 16px', borderBottom: `1px solid ${k.border}55` }}>
              <Num v={ceV} signed={isChange} side="ce" />
              <Bar pct={cePct} side="ce" negative={isChange && ceV < 0} />
              <div style={{ textAlign: 'center' }}>
                {r.isAtm
                  ? <span style={{ background: '#3c3c3c', color: 'var(--k-bg)', fontWeight: 600, fontSize: 11.5, padding: '2px 8px', borderRadius: 4 }}>{r.strike}</span>
                  : <span style={{ fontWeight: 600, color: 'var(--k-ink-1)', fontSize: 11.5, fontVariantNumeric: 'tabular-nums' }}>{r.strike}</span>}
              </div>
              <Bar pct={pePct} side="pe" negative={isChange && peV < 0} />
              <Num v={peV} signed={isChange} side="pe" />
            </div>
          );
        })}
      </div>

      {/* Footer stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', borderTop: `1px solid ${k.border}`, background: k.bg, padding: '10px 16px' }}>
        {(isChange
          ? [
              { label: 'Call ΔOI', value: (stats.ceChg > 0 ? '+' : '') + stats.ceChg.toFixed(2) },
              { label: 'Put ΔOI', value: (stats.peChg > 0 ? '+' : '') + stats.peChg.toFixed(2) },
              { label: 'PCR', value: stats.pcr ? stats.pcr.toFixed(2) : '–' },
              { label: 'Max Pain', value: stats.maxPain },
            ]
          : [
              { label: 'Call OI', value: stats.ceOi.toFixed(2) },
              { label: 'Put OI', value: stats.peOi.toFixed(2) },
              { label: 'PCR', value: stats.pcr ? stats.pcr.toFixed(2) : '–' },
              { label: 'Max Pain', value: stats.maxPain },
            ]
        ).map((s) => (
          <div key={s.label} style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: k.dim, marginBottom: 3 }}>{s.label}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--k-ink-1)', fontVariantNumeric: 'tabular-nums' }}>{s.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
