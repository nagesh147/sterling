import React, { useState } from 'react';
import { useKiteInstrumentSearch, useKiteQuote, useKiteOhlc, useKiteHistorical, useKiteWatchlist } from '../../hooks/useKite';
import { useDebounced } from '../../hooks/useDebounced';
import { MacChartSwitch } from './mac/MacChartSwitch';

function parseTs(ts: string): string {
  const nfoRe = /^([A-Z]+)(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d+)(CE|PE)$/;
  const nfoM = ts.match(nfoRe);
  if (nfoM) {
    const underlying = nfoM[1]; const yy = nfoM[2]; const strike = Number(nfoM[4]); const type = nfoM[5];
    const monIdx = { JAN:0,FEB:1,MAR:2,APR:3,MAY:4,JUN:5,JUL:6,AUG:7,SEP:8,OCT:9,NOV:10,DEC:11 }[nfoM[3]] ?? 0;
    const d = new Date(2000 + Number(yy), monIdx + 1, 0);
    const month = { JAN:'Jan',FEB:'Feb',MAR:'Mar',APR:'Apr',MAY:'May',JUN:'Jun',JUL:'Jul',AUG:'Aug',SEP:'Sep',OCT:'Oct',NOV:'Nov',DEC:'Dec' }[nfoM[3]] ?? nfoM[3];
    return `${underlying} ${strike} ${type} · ${d.getDate()} ${month} ${yy}`;
  }
  const bseRe = /^([A-Z]+)(\d{2})(\d)(\d{2})(\d+)(CE|PE)$/;
  const bseM = ts.match(bseRe);
  if (bseM) {
    const underlying = bseM[1]; const yy = bseM[2]; const mon = Number(bseM[3]);
    const day = Number(bseM[4]); const strike = Number(bseM[5]); const type = bseM[6];
    if (mon >= 1 && mon <= 12 && day >= 1 && day <= 31) {
      const d = new Date(2000 + Number(yy), mon - 1, day);
      const month = d.toLocaleString('en-US', { month: 'short' });
      return `${underlying} ${strike} ${type} · ${day} ${month} ${yy}`;
    }
    return ts;
  }
  const futRe = /^([A-Z]+)(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)FUT$/;
  const futM = ts.match(futRe);
  if (futM) {
    const underlying = futM[1]; const yy = futM[2];
    const monIdx = { JAN:0,FEB:1,MAR:2,APR:3,MAY:4,JUN:5,JUL:6,AUG:7,SEP:8,OCT:9,NOV:10,DEC:11 }[futM[3]] ?? 0;
    const d = new Date(2000 + Number(yy), monIdx + 1, 0);
    const month = { JAN:'Jan',FEB:'Feb',MAR:'Mar',APR:'Apr',MAY:'May',JUN:'Jun',JUL:'Jul',AUG:'Aug',SEP:'Sep',OCT:'Oct',NOV:'Nov',DEC:'Dec' }[futM[3]] ?? futM[3];
    return `${underlying} FUT · ${d.getDate()} ${month} ${yy}`;
  }
  return ts;
}

const S = {
  card: { background: '#fff', border: `1px solid #e0e0e0`, borderRadius: 4, padding: 14, marginBottom: 14 } as React.CSSProperties,
  title: { color: '#9b9b9b', fontSize: 11, letterSpacing: 1, marginBottom: 10, fontWeight: 700 } as React.CSSProperties,
  search: { background: '#f9f9f9', color: '#444', border: `1px solid #e0e0e0`, borderRadius: 4, padding: '10px 12px', fontFamily: 'inherit', fontSize: 14, width: '100%', boxSizing: 'border-box' as const } as React.CSSProperties,
  hint: { color: '#9b9b9b', fontSize: 11 } as React.CSSProperties,
  th: { textAlign: 'left' as const, color: '#9b9b9b', fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid #e0e0e0` } as React.CSSProperties,
  td: { padding: '6px 8px', fontSize: 12, color: '#444', borderBottom: `1px solid #e0e0e0` } as React.CSSProperties,
  input: { background: '#f9f9f9', color: '#444', border: `1px solid #e0e0e0`, borderRadius: 4, padding: '6px 9px', fontFamily: 'inherit', fontSize: 12, boxSizing: 'border-box' as const } as React.CSSProperties,
  label: { color: '#9b9b9b', fontSize: 10, letterSpacing: 1, marginBottom: 3, display: 'block' } as React.CSSProperties,
  btn: { background: '#f9f9f9', color: '#387ed1', border: `1px solid #387ed1`, padding: '6px 14px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 600 } as React.CSSProperties,
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 8 } as React.CSSProperties,
  tabRow: { display: 'flex', gap: 0, marginBottom: 12 } as React.CSSProperties,
};

function tabStyle(sel: boolean): React.CSSProperties {
  return {
    padding: '5px 14px', fontSize: 11, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
    background: sel ? '#fff' : 'transparent', color: sel ? '#444' : '#9b9b9b',
    border: `1px solid ${sel ? '#e0e0e0' : 'transparent'}`, borderRadius: 4,
  };
}

function pill(col: string): React.CSSProperties {
  return { background: '#f9f9f9', color: col, border: `1px solid ${col}`, padding: '1px 7px', borderRadius: 2, fontSize: 9, fontWeight: 700, whiteSpace: 'nowrap' };
}

const INTERVALS = ['minute', '3minute', '5minute', '15minute', '30minute', '60minute', 'day', 'week'];

function QuoteCard({ symbols }: { symbols: string[] }) {
  // Full-quote card shows the depth ladder — stream it live (full mode) so it
  // updates in real time instead of only on the slow quote-mode REST heartbeat.
  const { data, isLoading, error } = useKiteQuote(symbols, symbols.length > 0, 5_000, 'full');
  if (symbols.length === 0) return null;
  if (isLoading) return <div style={S.hint}>Loading quotes…</div>;
  if (error) return <div style={{ color: '#e53935', fontSize: 11 }}>✗ {(error as Error).message}</div>;
  if (!data || Object.keys(data).length === 0) return <div style={S.hint}>No quote data.</div>;

  return (
    <div style={{ marginTop: 8 }}>
      {Object.entries(data).map(([sym, q]: [string, any]) => (
        <div key={sym} style={{ border: `1px solid #e0e0e0`, borderRadius: 4, padding: 12, marginBottom: 10, background: '#f9f9f9' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span style={{ fontWeight: 800, color: '#444', fontSize: 14 }}>{sym}</span>
            {q.instrument_token && <span style={pill('#9b9b9b')}>{q.instrument_token}</span>}
          </div>
          <div style={S.grid}>
            <div><span style={S.label}>LTP</span><span style={{ color: '#444', fontWeight: 700, fontSize: 14 }}>₹{Number(q.last_price ?? 0).toLocaleString('en-IN')}</span></div>
            <div><span style={S.label}>Open</span><span style={{ color: '#444' }}>{Number(q.ohlc?.open ?? 0).toFixed(2)}</span></div>
            <div><span style={S.label}>High</span><span style={{ color: '#444' }}>{Number(q.ohlc?.high ?? 0).toFixed(2)}</span></div>
            <div><span style={S.label}>Low</span><span style={{ color: '#444' }}>{Number(q.ohlc?.low ?? 0).toFixed(2)}</span></div>
            <div><span style={S.label}>Close</span><span style={{ color: '#444' }}>{Number(q.ohlc?.close ?? 0).toFixed(2)}</span></div>
            <div><span style={S.label}>Change</span><span style={{ color: Number(q.net_change ?? 0) >= 0 ? '#4caf50' : '#e53935' }}>{Number(q.net_change ?? 0) >= 0 ? '+' : ''}{Number(q.net_change ?? 0).toFixed(2)}%</span></div>
            <div><span style={S.label}>Volume</span><span style={{ color: '#444' }}>{Number(q.volume ?? 0).toLocaleString('en-IN')}</span></div>
            <div><span style={S.label}>OI</span><span style={{ color: '#444' }}>{Number(q.oi ?? 0).toLocaleString('en-IN')}</span></div>
          </div>
          {q.depth && (
            <div style={{ marginTop: 8 }}>
              <div style={S.label}>Market depth</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 4 }}>
                <thead><tr><th style={S.th}>Bid</th><th style={{ ...S.th, textAlign: 'right' }}>Qty</th><th style={S.th}>Ask</th><th style={{ ...S.th, textAlign: 'right' }}>Qty</th></tr></thead>
                <tbody>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      <td style={{ ...S.td, color: '#4caf50' }}>{q.depth.buy?.[i]?.price?.toFixed(2) ?? '—'}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{q.depth.buy?.[i]?.quantity ?? '—'}</td>
                      <td style={{ ...S.td, color: '#e53935' }}>{q.depth.sell?.[i]?.price?.toFixed(2) ?? '—'}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{q.depth.sell?.[i]?.quantity ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function OhlcCard({ symbols }: { symbols: string[] }) {
  const { data, isLoading, error } = useKiteOhlc(symbols, symbols.length > 0);
  if (symbols.length === 0) return <div style={S.hint}>Select instruments for OHLC.</div>;
  if (isLoading) return <div style={S.hint}>Loading OHLC…</div>;
  if (error) return <div style={{ color: '#e53935', fontSize: 11 }}>✗ {(error as Error).message}</div>;
  if (!data) return null;

  return (
    <div style={{ marginTop: 8 }}>
      {Object.entries(data).map(([sym, o]: [string, any]) => {
        if (!o || typeof o !== 'object') return null;
        const cols = o.interval ? [o] : Object.values(o).filter((v: any) => v && typeof v === 'object');
        return (
          <div key={sym} style={{ border: `1px solid #e0e0e0`, borderRadius: 4, padding: 12, marginBottom: 10, background: '#f9f9f9' }}>
            <span style={{ fontWeight: 800, color: '#444', fontSize: 14 }}>{sym}</span>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 8 }}>
              <thead><tr>
                <th style={S.th}>Interval</th><th style={{ ...S.th, textAlign: 'right' }}>Open</th><th style={{ ...S.th, textAlign: 'right' }}>High</th><th style={{ ...S.th, textAlign: 'right' }}>Low</th><th style={{ ...S.th, textAlign: 'right' }}>Close</th>
                <th style={{ ...S.th, textAlign: 'right' }}>Volume</th><th style={{ ...S.th, textAlign: 'right' }}>OI</th>
              </tr></thead>
              <tbody>
                {cols.map((c: any, i: number) => (
                  <tr key={c.interval || i}>
                    <td style={S.td}>{c.interval}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{Number(c.open ?? 0).toFixed(2)}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{Number(c.high ?? 0).toFixed(2)}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{Number(c.low ?? 0).toFixed(2)}</td>
                    <td style={{ ...S.td, textAlign: 'right', fontWeight: 700 }}>{Number(c.close ?? 0).toFixed(2)}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{Number(c.volume ?? 0).toLocaleString('en-IN')}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{Number(c.open_interest ?? 0).toLocaleString('en-IN')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}

function HistoricalCard() {
  const [token, setToken] = useState('');
  const [interval, setInterval] = useState('day');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [continuous, setContinuous] = useState(false);
  const [oi, setOi] = useState(false);
  const [req, setReq] = useState<any>(null);

  const { data, isLoading, error } = useKiteHistorical(
    req ?? { token: 0, interval: 'day', from: '', to: '' },
    req != null,
  );

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 12 }}>
        <div>
          <label style={S.label}>Token</label>
          <input style={{ ...S.input, width: 130 }} value={token} onChange={(e) => setToken(e.target.value)} placeholder="e.g. 408065" />
        </div>
        <div>
          <label style={S.label}>Interval</label>
          <select style={S.input} value={interval} onChange={(e) => setInterval(e.target.value)}>
            {INTERVALS.map((iv) => <option key={iv} value={iv}>{iv}</option>)}
          </select>
        </div>
        <div>
          <label style={S.label}>From</label>
          <input style={{ ...S.input, width: 160 }} value={from} onChange={(e) => setFrom(e.target.value)} placeholder="YYYY-MM-DD HH:mm:ss" />
        </div>
        <div>
          <label style={S.label}>To</label>
          <input style={{ ...S.input, width: 160 }} value={to} onChange={(e) => setTo(e.target.value)} placeholder="YYYY-MM-DD HH:mm:ss" />
        </div>
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer', fontSize: 11, color: '#9b9b9b' }}>
          <input type="checkbox" checked={continuous} onChange={(e) => setContinuous(e.target.checked)} /> Continuous
        </label>
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer', fontSize: 11, color: '#9b9b9b' }}>
          <input type="checkbox" checked={oi} onChange={(e) => setOi(e.target.checked)} /> OI
        </label>
        <button style={S.btn} disabled={!token || !from || !to} onClick={() => setReq({ token: Number(token), interval, from, to, continuous, oi })}>Fetch</button>
      </div>
      {isLoading && <div style={S.hint}>Loading historical data…</div>}
      {error && <div style={{ color: '#e53935', fontSize: 11 }}>✗ {(error as Error).message}</div>}
      {data && (
        <div>
          <div style={{ ...S.hint, marginBottom: 6 }}>{Array.isArray(data) ? `${data.length} candles` : Object.keys(data).length > 0 ? 'Data loaded' : 'No data'}</div>
          {Array.isArray(data) && data.length > 0 && (
            <div style={{ overflow: 'auto', maxHeight: 420 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr>
                  <th style={S.th}>Time</th><th style={{ ...S.th, textAlign: 'right' }}>Open</th><th style={{ ...S.th, textAlign: 'right' }}>High</th><th style={{ ...S.th, textAlign: 'right' }}>Low</th><th style={{ ...S.th, textAlign: 'right' }}>Close</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>Volume</th><th style={{ ...S.th, textAlign: 'right' }}>OI</th>
                </tr></thead>
                <tbody>
                  {data.slice(-200).map((c: any, i: number) => (
                    <tr key={i}>
                      <td style={{ ...S.td, color: '#9b9b9b', fontSize: 10 }}>{c[0]}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{Number(c[1]).toFixed(2)}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{Number(c[2]).toFixed(2)}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{Number(c[3]).toFixed(2)}</td>
                      <td style={{ ...S.td, textAlign: 'right', fontWeight: 700 }}>{Number(c[4]).toFixed(2)}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{Number(c[5]).toLocaleString('en-IN')}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{c[6] != null ? Number(c[6]).toLocaleString('en-IN') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function MarketDataPane() {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounced(query, 300);
  const search = useKiteInstrumentSearch(debouncedQuery);
  const { items: watch, add } = useKiteWatchlist();
  const [selected, setSelected] = useState<string[]>([]);
  const [tab, setTab] = useState<'quote' | 'ohlc' | 'historical'>('quote');

  const toggleSymbol = (sym: string) => {
    setSelected((p) => p.includes(sym) ? p.filter((s) => s !== sym) : [...p, sym]);
  };

  return (
    <div style={{ padding: '24px 32px' }}>
      <div style={S.card}>
        <div style={S.title}>SEARCH & SELECT</div>
        <input
          style={S.search}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search"
          autoFocus
        />
        {search.isFetching && query.trim().length >= 2 && <div style={{ ...S.hint, marginTop: 8 }}>Searching…</div>}
        {search.error && <div style={{ color: '#e53935', fontSize: 11, marginTop: 8 }}>✗ {(search.error as Error).message}</div>}
        {search.data && query.trim().length >= 2 && (
          <div style={{ marginTop: 8, maxHeight: 300, overflow: 'auto', border: `1px solid #e0e0e0`, borderRadius: 4 }}>
            {search.data.instruments.map((i) => {
              const sym = `${i.exchange || 'NSE'}:${i.tradingsymbol}`;
              const sel = selected.includes(sym);
              const inWatch = watch.some((w) => w.symbol === sym);
              return (
                <div key={`${i.exchange}:${i.instrument_token}`} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 10px', cursor: 'pointer',
                  borderBottom: `1px solid #e0e0e0`,
                  background: sel ? '#e3f2fd' : inWatch ? '#e8f5e9' : 'transparent',
                }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                    <span style={{ color: '#444', fontWeight: 700, fontSize: 13 }}>{parseTs(i.tradingsymbol)}</span>
                    <span style={{ ...S.hint, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{i.name} · {i.exchange} · token {i.instrument_token}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                    {!inWatch && <span style={{ ...S.hint, fontSize: 10, cursor: 'pointer' }} onClick={() => add({ symbol: sym, token: i.instrument_token, name: i.name || i.tradingsymbol, sub: `${i.exchange}`, expiry: i.expiry })}>+watch</span>}
                    <span onClick={() => toggleSymbol(sym)} style={{ color: sel ? '#387ed1' : '#9b9b9b', fontSize: 18, lineHeight: 1 }}>{sel ? '◉' : '○'}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {selected.length > 0 && (
          <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={S.hint}>{selected.length} selected:</span>
            {selected.map((s) => (
              <span key={s} style={{ background: '#f9f9f9', color: '#387ed1', border: `1px solid #387ed1`, borderRadius: 2, padding: '2px 8px', fontSize: 10, fontWeight: 600, cursor: 'pointer' }} onClick={() => toggleSymbol(s)}>{s} ✕</span>
            ))}
          </div>
        )}
      </div>

      <div style={S.card}>
        <div style={S.tabRow}>
          <button style={tabStyle(tab === 'quote')} onClick={() => setTab('quote')}>FULL QUOTE</button>
          <button style={tabStyle(tab === 'ohlc')} onClick={() => setTab('ohlc')}>OHLC</button>
          <button style={tabStyle(tab === 'historical')} onClick={() => setTab('historical')}>HISTORICAL</button>
        </div>
        <MacChartSwitch switchKey={tab === 'historical' ? 'historical' : `${tab}:${selected.join(',')}`}>
          {tab === 'quote' && <QuoteCard symbols={selected} />}
          {tab === 'ohlc' && <OhlcCard symbols={selected} />}
          {tab === 'historical' && <HistoricalCard />}
        </MacChartSwitch>
      </div>
    </div>
  );
}
