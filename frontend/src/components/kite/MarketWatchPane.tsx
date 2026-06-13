import React, { useMemo, useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import { useKiteInstrumentSearch, useKiteLtp, useKiteWatchlist, useSyncKiteWatchlist } from '../../hooks/useKite';
import type { KiteInstrument } from '../../types/kite';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  search: { background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 8, padding: '10px 12px', fontFamily: 'inherit', fontSize: 14, width: '100%', boxSizing: 'border-box' as const },
  resRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 10px', cursor: 'pointer', borderBottom: `1px solid ${tint(t.border, 50)}` },
  th: { textAlign: 'left' as const, color: t.dim, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', fontSize: 12, color: t.bright, borderBottom: `1px solid ${tint(t.border, 50)}` },
  hint: { color: t.dim, fontSize: 11 },
};

function pill(col: string): React.CSSProperties {
  return { background: tint(col, 13), color: col, border: `1px solid ${col}`, padding: '1px 7px', borderRadius: 999, fontSize: 9, fontWeight: 700, whiteSpace: 'nowrap' };
}

function exColor(ex: string): string {
  switch ((ex || '').toUpperCase()) {
    case 'NSE': return t.blue;
    case 'BSE': return t.cyan;
    case 'NFO': case 'BFO': return t.purple;
    case 'MCX': return t.amber;
    case 'CDS': return t.green;
    default: return t.dim;
  }
}

function instrMeta(i: KiteInstrument) {
  const ty = (i.instrument_type || '').toUpperCase();
  let kind = ty || (i.segment || '').toUpperCase();
  let detail = i.name || '';
  if (ty === 'CE' || ty === 'PE') {
    kind = ty;
    detail = `${i.name || ''} ${i.strike ?? ''} ${ty}${i.expiry ? ' · ' + i.expiry : ''}`.trim();
  } else if (ty === 'FUT') {
    kind = 'FUT';
    detail = `${i.name || ''} FUT${i.expiry ? ' · ' + i.expiry : ''}`.trim();
  } else if (ty === 'EQ' || kind === 'NSE' || kind === 'BSE') {
    kind = 'EQ';
  }
  return { kind, detail };
}

const num = (v: any) => Number(v ?? 0);

export function MarketWatchPane() {
  const [query, setQuery] = useState('');
  const search = useKiteInstrumentSearch(query);
  const { items: watch, add, remove } = useKiteWatchlist();
  const sync = useSyncKiteWatchlist();

  const symbols = useMemo(() => watch.map((w) => w.symbol), [watch]);
  const { data: ltp } = useKiteLtp(symbols, symbols.length > 0);

  const addInstr = (i: KiteInstrument) => {
    const { kind } = instrMeta(i);
    const sym = `${i.exchange || 'NSE'}:${i.tradingsymbol}`;
    add({ symbol: sym, token: i.instrument_token, name: i.name || i.tradingsymbol, sub: `${i.exchange} · ${kind}` });
  };

  return (
    <div>
      <div style={S.card}>
        <div style={S.title}>SEARCH — STOCKS · FUTURES · OPTIONS · INDICES</div>
        <input
          style={S.search}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search anything — e.g. INFY, NIFTY 25000 CE, BANKNIFTY FUT, CRUDEOIL…"
          autoFocus
        />
        {query.trim().length > 0 && query.trim().length < 2 && (
          <div style={{ ...S.hint, marginTop: 8 }}>Keep typing… (min 2 characters)</div>
        )}
        {search.isFetching && query.trim().length >= 2 && <div style={{ ...S.hint, marginTop: 8 }}>Searching…</div>}
        {search.error && <div style={{ color: t.red, fontSize: 11, marginTop: 8 }}>✗ {(search.error as Error).message}</div>}
        {search.data && query.trim().length >= 2 && (
          <div style={{ marginTop: 8, maxHeight: 360, overflow: 'auto', border: `1px solid ${t.border}`, borderRadius: 6 }}>
            {search.data.instruments.map((i) => {
              const { kind, detail } = instrMeta(i);
              const sym = `${i.exchange || 'NSE'}:${i.tradingsymbol}`;
              const added = watch.some((w) => w.symbol === sym);
              return (
                <div
                  key={`${i.exchange}:${i.instrument_token}`}
                  style={{ ...S.resRow, background: added ? tint(t.green, 6) : 'transparent' }}
                  onMouseEnter={(e) => { if (!added) (e.currentTarget as HTMLElement).style.background = tint(t.blue, 8); }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = added ? tint(t.green, 6) : 'transparent'; }}
                  onClick={() => !added && addInstr(i)}
                  title={added ? 'Already in watchlist' : 'Add to watchlist'}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                    <span style={{ color: t.bright, fontWeight: 700, fontSize: 13 }}>{i.tradingsymbol}</span>
                    <span style={{ ...S.hint, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{detail || i.name}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                    <span style={pill(exColor(i.exchange || ''))}>{i.exchange}</span>
                    <span style={pill(t.dim)}>{kind}</span>
                    <span style={{ color: added ? t.green : t.blue, fontSize: 16, width: 16, textAlign: 'center' }}>{added ? '✓' : '+'}</span>
                  </div>
                </div>
              );
            })}
            {search.data.instruments.length === 0 && <div style={{ ...S.hint, padding: 10 }}>No matches.</div>}
          </div>
        )}
      </div>

      <div style={S.card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={S.title}>WATCHLIST · LIVE LTP</div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              style={{ ...pill(t.blue), cursor: 'pointer', fontFamily: 'inherit', padding: '4px 10px', fontSize: 10 }}
              disabled={sync.isPending}
              title="Add your Kite holdings, positions & GTT instruments to the watchlist (needs a connected live session)"
              onClick={() => sync.mutate(undefined, { onSuccess: (d) => d.items.forEach(add) })}
            >
              {sync.isPending ? 'Syncing…' : '⟳ Sync from Kite'}
            </button>
            {watch.length > 0 && <span style={S.hint}>{watch.length} saved</span>}
          </div>
        </div>
        {sync.isSuccess && (
          <div style={{ ...S.hint, marginTop: 6, lineHeight: 1.6 }}>
            ✓ Synced {sync.data.count} from your account
            {sync.data.count > 0 && ` (${Object.entries(sync.data.sources).map(([k, v]) => `${v} ${k}`).join(', ')})`}. {sync.data.note}
          </div>
        )}
        {sync.isError && <div style={{ color: t.red, fontSize: 11, marginTop: 6 }}>✗ {sync.error.message}</div>}
        {watch.length === 0 && <div style={S.hint}>Search above and click a result to add it, or ⟳ Sync from Kite. Your watchlist is saved automatically.</div>}
        {watch.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Symbol</th><th style={S.th}>Detail</th>
              <th style={{ ...S.th, textAlign: 'right' }}>LTP</th><th style={S.th} />
            </tr></thead>
            <tbody>
              {watch.map((w) => (
                <tr key={w.symbol}>
                  <td style={{ ...S.td, fontWeight: 700 }}>{w.symbol}</td>
                  <td style={{ ...S.td, color: t.dim }}>{w.sub || w.name}</td>
                  <td style={{ ...S.td, textAlign: 'right', fontWeight: 700 }}>
                    {ltp?.[w.symbol]?.last_price != null ? `₹${num(ltp[w.symbol].last_price).toLocaleString('en-IN')}` : '—'}
                  </td>
                  <td style={{ ...S.td, textAlign: 'right' }}>
                    <span style={{ cursor: 'pointer', color: t.red }} onClick={() => remove(w.symbol)}>✕</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div style={{ ...S.hint, marginTop: 8 }}>Prices poll every 5s (needs a connected live session). Watchlist persists across tabs &amp; refresh.</div>
      </div>
    </div>
  );
}
