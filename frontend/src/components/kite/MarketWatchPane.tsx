import React, { useMemo, useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import { useKiteInstrumentSearch, useKiteLtp } from '../../hooks/useKite';

const EXCHANGES = ['NSE', 'NFO', 'BSE', 'MCX', 'CDS'];

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  input: { background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: '7px 9px', fontFamily: 'inherit', fontSize: 12, flex: 1 },
  select: { background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: '7px 9px', fontFamily: 'inherit', fontSize: 12 },
  resRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 8px', borderRadius: 6, cursor: 'pointer', fontSize: 12 },
  th: { textAlign: 'left' as const, color: t.dim, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', fontSize: 12, color: t.bright, borderBottom: `1px solid ${tint(t.border, 50)}` },
  hint: { color: t.dim, fontSize: 11 },
};

interface WatchItem { symbol: string; token: number; name: string; }

export function MarketWatchPane() {
  const [exchange, setExchange] = useState('NSE');
  const [query, setQuery] = useState('');
  const [watch, setWatch] = useState<WatchItem[]>([]);
  const search = useKiteInstrumentSearch(query, exchange);

  const symbols = useMemo(() => watch.map((w) => w.symbol), [watch]);
  const { data: ltp } = useKiteLtp(symbols, symbols.length > 0);

  const add = (sym: string, token: number, name: string) => {
    setWatch((w) => (w.some((x) => x.symbol === sym) ? w : [...w, { symbol: sym, token, name }]));
  };
  const remove = (sym: string) => setWatch((w) => w.filter((x) => x.symbol !== sym));

  return (
    <div>
      <div style={S.card}>
        <div style={S.title}>SEARCH INSTRUMENTS</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <select style={S.select} value={exchange} onChange={(e) => setExchange(e.target.value)}>
            {EXCHANGES.map((x) => <option key={x} value={x}>{x}</option>)}
          </select>
          <input style={S.input} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Type a symbol or name (min 2 chars)…" />
        </div>
        {search.isLoading && <div style={{ ...S.hint, marginTop: 8 }}>Searching…</div>}
        {search.error && <div style={{ color: t.red, fontSize: 11, marginTop: 8 }}>✗ {(search.error as Error).message}</div>}
        {search.data && (
          <div style={{ marginTop: 8, maxHeight: 240, overflow: 'auto' }}>
            {search.data.instruments.map((i) => {
              const sym = `${i.exchange || exchange}:${i.tradingsymbol}`;
              return (
                <div key={i.instrument_token} style={S.resRow}
                  onMouseEnter={(e) => (e.currentTarget.style.background = tint(t.blue, 8))}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  onClick={() => add(sym, i.instrument_token, i.name || i.tradingsymbol)}>
                  <span style={{ color: t.bright }}>{i.tradingsymbol}</span>
                  <span style={S.hint}>{i.name} · +add</span>
                </div>
              );
            })}
            {search.data.instruments.length === 0 && <div style={S.hint}>No matches.</div>}
          </div>
        )}
      </div>

      <div style={S.card}>
        <div style={S.title}>WATCHLIST · LIVE LTP</div>
        {watch.length === 0 && <div style={S.hint}>Search above and click a result to add it.</div>}
        {watch.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr><th style={S.th}>Symbol</th><th style={S.th}>Name</th><th style={{ ...S.th, textAlign: 'right' }}>LTP</th><th style={S.th} /></tr></thead>
            <tbody>
              {watch.map((w) => (
                <tr key={w.symbol}>
                  <td style={S.td}>{w.symbol}</td>
                  <td style={{ ...S.td, color: t.dim }}>{w.name}</td>
                  <td style={{ ...S.td, textAlign: 'right', fontWeight: 700 }}>
                    {ltp?.[w.symbol]?.last_price != null ? `₹${Number(ltp[w.symbol].last_price).toLocaleString('en-IN')}` : '—'}
                  </td>
                  <td style={{ ...S.td, textAlign: 'right' }}>
                    <span style={{ cursor: 'pointer', color: t.red }} onClick={() => remove(w.symbol)}>✕</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div style={{ ...S.hint, marginTop: 8 }}>Prices poll every 5s. Live binary ticks (KiteTicker) stream once a live session is connected.</div>
      </div>
    </div>
  );
}
