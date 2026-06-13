import React, { useMemo, useState } from 'react';
import { k as t, tint, kStyles, Icons } from '../../styles/kiteUI';
import { useKiteInstrumentSearch, useKiteLtp, useKiteQuote, useKiteWatchlist, useSyncKiteWatchlist } from '../../hooks/useKite';
import type { KiteInstrument } from '../../types/kite';

const S = {
  container: { display: 'flex', flexDirection: 'column' as const, height: '100%', background: t.bg, fontFamily: t.fontFamily },
  searchContainer: { padding: '12px 16px', borderBottom: `1px solid ${t.border}`, background: t.bg, display: 'flex', gap: 12, alignItems: 'center', position: 'sticky' as const, top: 0, zIndex: 10 },
  search: { flex: 1, background: t.bg, color: t.text, border: 'none', padding: '8px 32px 8px 12px', fontFamily: 'inherit', fontSize: 13, outline: 'none' },
  listContainer: { flex: 1, overflowY: 'auto' as const },
  resRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 16px', cursor: 'pointer', borderBottom: `1px solid ${t.border}`, background: t.bg },
  hint: { color: t.dim, fontSize: 12 },
  btnAction: { display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: 2, cursor: 'pointer', fontSize: 12, fontWeight: 600, border: 'none' },
};

function pillStyle(col: string): React.CSSProperties {
  return kStyles.pill(col);
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
  if (ty === 'CE' || ty === 'PE') {
    kind = ty;
  } else if (ty === 'FUT') {
    kind = 'FUT';
  } else if (ty === 'EQ' || kind === 'NSE' || kind === 'BSE') {
    kind = 'EQ';
  }
  const detail = parseTradingsymbol(i.tradingsymbol);
  return { kind, detail };
}

const num = (v: any) => Number(v ?? 0);

function parseTradingsymbol(ts: string): string {
  const nseMatch = ts.match(/^([A-Z]+)(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d+)(CE|PE)$/);
  if (nseMatch) {
    const underlying = nseMatch[1];
    const yy = nseMatch[2];
    const mon3 = nseMatch[3];
    const strike = Number(nseMatch[4]);
    const type = nseMatch[5];
    return `${underlying} ${strike} ${type}`;
  }
  const bseMatch = ts.match(/^([A-Z]+)(\d{2})(\d)(\d{2})(\d+)(CE|PE)$/);
  if (bseMatch) {
    return `${bseMatch[1]} ${Number(bseMatch[5])} ${bseMatch[6]}`;
  }
  const futMatch = ts.match(/^([A-Z]+)(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)FUT$/);
  if (futMatch) {
    return `${futMatch[1]} FUT`;
  }
  return ts;
}

function chgPct(q: any): { value: number | null; abs: number | null; color: string } {
  if (q?.ohlc?.close && q?.last_price) {
    const abs = q.last_price - q.ohlc.close;
    const chg = (abs / q.ohlc.close) * 100;
    return { value: chg, abs, color: chg >= 0 ? t.green : t.red };
  }
  if (q?.net_change != null) {
    return { value: q.net_change, abs: null, color: q.net_change >= 0 ? t.green : t.red };
  }
  return { value: null, abs: null, color: t.dim };
}

function formatPrice(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return '—';
  return v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ─── Expanded Quote Row ──────────────────────────────────────────────────────

function QuoteDetail({ sym, q }: { sym: string; q: any }) {
  if (!q || typeof q !== 'object') return null;
  const chg = chgPct(q);
  
  // Fake total quantities for progress bar scale
  const totalBuy = num(q.buy_quantity) || 100000;
  const totalSell = num(q.sell_quantity) || 100000;

  return (
    <div style={{ padding: '16px', background: t.surface, borderBottom: `1px solid ${t.border}`, fontFamily: t.fontFamily }}>
      {/* ── Market Depth ── */}
      {q.depth?.buy?.length > 0 && q.depth?.sell?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 8px', borderBottom: `1px solid ${t.border}`, color: t.dim, fontSize: 11, background: t.surface }}>
                <span style={{flex: 1, textAlign: 'left'}}>Bid</span><span style={{flex: 1, textAlign: 'right'}}>Orders</span><span style={{flex: 1, textAlign: 'right'}}>Qty.</span>
              </div>
              {Array.from({ length: 5 }).map((_, i) => {
                const bid = q.depth.buy[i] || {};
                const qty = num(bid.quantity || bid.qty);
                const pct = totalBuy > 0 ? (qty / totalBuy) * 100 : 0;
                return (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 8px', fontSize: 12, position: 'relative' }}>
                    <div style={{ position: 'absolute', top: 0, right: 0, bottom: 0, width: `${Math.min(100, pct * 5)}%`, background: tint(t.blue, 6), zIndex: 0 }} />
                    <span style={{ color: t.blue, flex: 1, textAlign: 'left', zIndex: 1 }}>{bid.price ? formatPrice(Number(bid.price)) : '—'}</span>
                    <span style={{ color: t.dim, flex: 1, textAlign: 'right', zIndex: 1 }}>{bid.orders ?? '—'}</span>
                    <span style={{ color: t.text, flex: 1, textAlign: 'right', zIndex: 1 }}>{qty.toLocaleString('en-IN')}</span>
                  </div>
                );
              })}
            </div>
            <div style={{ width: 1, background: t.border }} />
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 8px', borderBottom: `1px solid ${t.border}`, color: t.dim, fontSize: 11, background: t.surface }}>
                <span style={{flex: 1, textAlign: 'left'}}>Offer</span><span style={{flex: 1, textAlign: 'right'}}>Orders</span><span style={{flex: 1, textAlign: 'right'}}>Qty.</span>
              </div>
              {Array.from({ length: 5 }).map((_, i) => {
                const ask = q.depth.sell[i] || {};
                const qty = num(ask.quantity || ask.qty);
                const pct = totalSell > 0 ? (qty / totalSell) * 100 : 0;
                return (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 8px', fontSize: 12, position: 'relative' }}>
                    <div style={{ position: 'absolute', top: 0, left: 0, bottom: 0, width: `${Math.min(100, pct * 5)}%`, background: tint(t.red, 6), zIndex: 0 }} />
                    <span style={{ color: t.red, flex: 1, textAlign: 'left', zIndex: 1 }}>{ask.price ? formatPrice(Number(ask.price)) : '—'}</span>
                    <span style={{ color: t.dim, flex: 1, textAlign: 'right', zIndex: 1 }}>{ask.orders ?? '—'}</span>
                    <span style={{ color: t.text, flex: 1, textAlign: 'right', zIndex: 1 }}>{qty.toLocaleString('en-IN')}</span>
                  </div>
                );
              })}
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px', fontSize: 12, borderTop: `1px solid ${t.border}`, borderBottom: `1px solid ${t.border}` }}>
            <span style={{ color: t.blue, flex: 1 }}>Total</span>
            <span style={{ color: t.blue, fontWeight: 500, flex: 1, textAlign: 'right' }}>{num(q.buy_quantity).toLocaleString('en-IN')}</span>
            <span style={{ width: 1 }} />
            <span style={{ color: t.red, flex: 1, paddingLeft: 8 }}>Total</span>
            <span style={{ color: t.red, fontWeight: 500, flex: 1, textAlign: 'right' }}>{num(q.sell_quantity).toLocaleString('en-IN')}</span>
          </div>
        </div>
      )}

      {/* ── Key stats grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px 32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: `1px solid ${t.border}`, paddingBottom: 4 }}>
          <span style={{ color: t.dim }}>Open</span><span style={{ color: t.text }}>{formatPrice(q.ohlc?.open)}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: `1px solid ${t.border}`, paddingBottom: 4 }}>
          <span style={{ color: t.dim }}>Prev. Close</span><span style={{ color: t.text }}>{formatPrice(q.ohlc?.close)}</span>
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: `1px solid ${t.border}`, paddingBottom: 4 }}>
          <span style={{ color: t.dim }}>Low</span><span style={{ color: t.text }}>{formatPrice(q.ohlc?.low)}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: `1px solid ${t.border}`, paddingBottom: 4 }}>
          <span style={{ color: t.dim }}>High</span><span style={{ color: t.text }}>{formatPrice(q.ohlc?.high)}</span>
        </div>

        {/* Progress Bar */}
        <div style={{ gridColumn: '1 / -1', padding: '2px 0 8px 0' }}>
           <div style={{ height: 4, background: t.border, borderRadius: 2, position: 'relative' }}>
              <div style={{ position: 'absolute', left: '20%', right: '30%', top: 0, bottom: 0, background: t.red, borderRadius: 2 }} />
           </div>
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: `1px solid ${t.border}`, paddingBottom: 4 }}>
          <span style={{ color: t.dim }}>Volume</span><span style={{ color: t.text }}>{q.volume != null ? num(q.volume).toLocaleString('en-IN') : 'N/A'}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: `1px solid ${t.border}`, paddingBottom: 4 }}>
          <span style={{ color: t.dim }}>Avg. price</span><span style={{ color: t.text }}>{formatPrice(q.average_price) || 'N/A'}</span>
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: `1px solid ${t.border}`, paddingBottom: 4 }}>
          <span style={{ color: t.dim }}>Lower circuit</span><span style={{ color: t.text }}>{formatPrice(q.lower_circuit_limit) || 'N/A'}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: `1px solid ${t.border}`, paddingBottom: 4 }}>
          <span style={{ color: t.dim }}>Upper circuit</span><span style={{ color: t.text }}>{formatPrice(q.upper_circuit_limit) || 'N/A'}</span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: `1px solid ${t.border}`, paddingBottom: 4 }}>
          <span style={{ color: t.dim }}>LTQ</span><span style={{ color: t.text }}>{q.last_quantity || 'N/A'}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: `1px solid ${t.border}`, paddingBottom: 4 }}>
          <span style={{ color: t.dim }}>LTT</span><span style={{ color: t.text }}>{q.last_trade_time ? new Date(q.last_trade_time).toLocaleTimeString() : 'N/A'}</span>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function MarketWatchPane({ onOpenInstrument }: { onOpenInstrument?: (symbol: string, defaultTab: 'chart' | 'option-chain') => void }) {
  const [query, setQuery] = useState('');
  const search = useKiteInstrumentSearch(query);
  const { items: watch, add, remove } = useKiteWatchlist();
  const sync = useSyncKiteWatchlist();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [hovered, setHovered] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState<{ symbol: string; top: number; left: number } | null>(null);

  React.useEffect(() => {
    const closeMenu = () => setMenuOpen(null);
    window.addEventListener('click', closeMenu);
    return () => window.removeEventListener('click', closeMenu);
  }, []);

  const handleMenuClick = (e: React.MouseEvent, symbol: string) => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setMenuOpen({ symbol, top: rect.bottom + 4, left: rect.left });
  };

  const symbols = useMemo(() => watch.map((w) => w.symbol), [watch]);
  const { data: ltp } = useKiteLtp(symbols, symbols.length > 0);
  const { data: quotes } = useKiteQuote(symbols, symbols.length > 0);

  const toggleExpand = (sym: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(sym)) next.delete(sym); else next.add(sym);
      return next;
    });
  };

  const addInstr = (i: KiteInstrument) => {
    const meta = instrMeta(i);
    const sym = `${i.exchange || 'NSE'}:${i.tradingsymbol}`;
    const label = meta.detail
      ? `${i.name || meta.detail}`
      : `${i.exchange} · ${meta.kind}`;
    add({ symbol: sym, token: i.instrument_token, name: meta.detail || i.tradingsymbol, sub: label });
    setQuery('');
  };

  return (
    <div style={S.container}>
      <div style={S.searchContainer}>
        <div style={{ position: 'relative', flex: 1, display: 'flex', alignItems: 'center', borderBottom: `1px solid ${t.border}` }}>
          <span style={{ position: 'absolute', left: 8, color: t.dim }}><Icons.Search /></span>
          <input
            style={S.search}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search eg: infy bse, nifty fut, nifty 22nd oct 14500 ce"
            autoFocus
          />
        </div>
        <span style={{ color: t.dim, fontSize: 12, cursor: 'pointer' }}>{watch.length} / 50</span>
      </div>

      <div style={S.listContainer}>
        {query.trim().length > 0 ? (
          <div>
            {search.isFetching && query.trim().length >= 2 && <div style={{ padding: 16, color: t.dim, fontSize: 13 }}>Searching…</div>}
            {search.error && <div style={{ padding: 16, color: t.red, fontSize: 13 }}>✗ {(search.error as Error).message}</div>}
            {search.data && query.trim().length >= 2 && (
              <div>
                {search.data.instruments.map((i) => {
                  const { kind, detail } = instrMeta(i);
                  const sym = `${i.exchange || 'NSE'}:${i.tradingsymbol}`;
                  const added = watch.some((w) => w.symbol === sym);
                  return (
                    <div
                      key={`${i.exchange}:${i.instrument_token}`}
                      style={{ ...S.resRow, background: added ? tint(t.green, 4) : t.bg }}
                      onMouseEnter={(e) => { if (!added) (e.currentTarget as HTMLElement).style.background = tint(t.blue, 4); }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = added ? tint(t.green, 4) : t.bg; }}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                        <span style={{ color: t.text, fontWeight: 500, fontSize: 13 }}>{i.tradingsymbol}</span>
                        <span style={{ color: t.dim, fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{detail || i.name}</span>
                      </div>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                        <span style={pillStyle(t.dim)}>{kind}</span>
                        <span style={pillStyle(exColor(i.exchange || ''))}>{i.exchange}</span>
                        {added ? (
                          <span style={{ color: t.green, fontSize: 16, width: 24, textAlign: 'center' }}>✓</span>
                        ) : (
                          <button style={{ ...S.btnAction, background: t.blue, color: '#fff', width: 24, height: 24 }} onClick={() => addInstr(i)}>+</button>
                        )}
                      </div>
                    </div>
                  );
                })}
                {search.data.instruments.length === 0 && <div style={{ padding: 16, color: t.dim, fontSize: 13 }}>No matches found.</div>}
              </div>
            )}
          </div>
        ) : (
          <div>
            {watch.length === 0 && (
              <div style={{ padding: 32, textAlign: 'center', color: t.dim, fontSize: 13 }}>
                <p style={{ marginBottom: 16 }}>Nothing here.</p>
                <p>Use the search bar to add instruments.</p>
                <button
                  style={{ marginTop: 24, padding: '8px 16px', background: t.surface, border: `1px solid ${t.border}`, borderRadius: 4, color: t.blue, cursor: 'pointer', fontSize: 13 }}
                  disabled={sync.isPending}
                  onClick={() => sync.mutate(undefined, { onSuccess: (d) => d.items.forEach(add) })}
                >
                  {sync.isPending ? 'Syncing…' : 'Sync holdings from Kite'}
                </button>
              </div>
            )}
            {watch.map((w) => {
              const q = quotes?.[w.symbol];
              const chg = q ? chgPct(q) : { value: null, abs: null, color: t.dim };
              const isExp = expanded.has(w.symbol);
              const isHovered = hovered === w.symbol;
              const lastPx = q?.last_price ?? ltp?.[w.symbol]?.last_price;
              const chgVal = chg.value;
              const chgAbs = chg.abs;
              const chgColor = chg.color;
              const rawTs = w.symbol.split(':')[1] || w.symbol;
              const displayName = parseTradingsymbol(rawTs);
              const exch = w.symbol.split(':')[0] || '';

              return (
                <div key={w.symbol}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '12px 16px',
                      cursor: 'pointer',
                      borderBottom: `1px solid ${t.border}`,
                      background: isHovered || isExp ? t.surface : t.bg,
                      transition: 'background 0.2s',
                    }}
                    onMouseEnter={() => setHovered(w.symbol)}
                    onMouseLeave={() => setHovered(null)}
                    onClick={() => toggleExpand(w.symbol)}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <span style={{ color: chgColor, fontWeight: 500, fontSize: 13, display: 'flex', gap: 6, alignItems: 'baseline' }}>
                        {displayName}
                        <span style={{ fontSize: 10, color: t.dim, fontWeight: 400 }}>{w.sub || w.name}</span>
                      </span>
                      <span style={pillStyle(exColor(exch))}>{exch}</span>
                    </div>

                    {isHovered ? (
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }} onClick={(e) => e.stopPropagation()}>
                        <button style={{ ...S.btnAction, background: t.blue, color: '#fff', fontSize: 13 }} title="Buy">B</button>
                        <button style={{ ...S.btnAction, background: t.red, color: '#fff', fontSize: 13 }} title="Sell">S</button>
                        <button style={{ ...S.btnAction, background: 'transparent', color: t.text, border: `1px solid ${t.border}` }} onClick={() => toggleExpand(w.symbol)} title="Market Depth"><Icons.Depth /></button>
                        <button style={{ ...S.btnAction, background: 'transparent', color: t.text, border: `1px solid ${t.border}` }} onClick={() => onOpenInstrument?.(w.symbol, 'chart')} title="Chart"><Icons.Chart /></button>
                        <button style={{ ...S.btnAction, background: 'transparent', color: t.text, border: `1px solid ${t.border}` }} onClick={() => remove(w.symbol)} title="Delete"><Icons.Trash /></button>
                        <button style={{ ...S.btnAction, background: 'transparent', color: t.text, border: `1px solid ${t.border}` }} onClick={(e) => handleMenuClick(e, w.symbol)} title="More"><Icons.More /></button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
                        <span style={{ color: chgColor, fontWeight: 500, fontSize: 13 }}>
                          {lastPx != null ? formatPrice(lastPx) : '—'}
                          {isExp && <span style={{ color: t.dim, fontSize: 10, marginLeft: 6 }}>{isExp ? '▾' : '▸'}</span>}
                        </span>
                        <span style={{ fontSize: 11, color: t.dim }}>
                          {chgAbs != null && chgVal != null ? (
                            <span>{chgAbs >= 0 ? '+' : ''}{chgAbs.toFixed(2)} <span style={{ color: chgColor }}>({chgVal.toFixed(2)}%)</span></span>
                          ) : (
                            '—'
                          )}
                        </span>
                      </div>
                    )}
                  </div>
                  {isExp && <QuoteDetail sym={w.symbol} q={quotes?.[w.symbol]} />}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── More Options Menu ── */}
      {menuOpen && (
        <div
          style={{
            position: 'fixed',
            top: menuOpen.top,
            left: menuOpen.left - 100, // align leftwards to fit within screen
            background: t.surface,
            border: `1px solid ${t.border}`,
            borderRadius: 4,
            boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
            padding: '8px 0',
            zIndex: 100,
            minWidth: 160,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div style={{ padding: '8px 16px', fontSize: 13, color: t.text, cursor: 'pointer', display: 'flex', gap: 12, alignItems: 'center' }} onClick={() => { onOpenInstrument?.(menuOpen.symbol, 'chart'); setMenuOpen(null); }}><span style={{ color: t.dim }}><Icons.Chart /></span> Chart</div>
          <div style={{ padding: '8px 16px', fontSize: 13, color: t.text, cursor: 'pointer', display: 'flex', gap: 12, alignItems: 'center' }} onClick={() => { onOpenInstrument?.(menuOpen.symbol, 'option-chain'); setMenuOpen(null); }}><span style={{ color: t.dim }}><Icons.OptionChain /></span> Option chain</div>
          <div style={{ padding: '8px 16px', fontSize: 13, color: t.text, cursor: 'pointer', display: 'flex', gap: 12, alignItems: 'center' }} onClick={() => { toggleExpand(menuOpen.symbol); setMenuOpen(null); }}><span style={{ color: t.dim }}><Icons.Depth /></span> Market depth</div>
          <div style={{ padding: '8px 16px', fontSize: 13, color: t.text, cursor: 'pointer', display: 'flex', gap: 12, alignItems: 'center' }} onClick={() => setMenuOpen(null)}><span style={{ color: t.dim }}><Icons.Pin /></span> Pin</div>
        </div>
      )}
    </div>
  );
}
