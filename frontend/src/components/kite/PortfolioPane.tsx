import React, { useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import {
  useConvertKitePosition, useKiteHoldings, useKitePositions,
  useKiteAuctions, useInitiateHoldingsAuth,
} from '../../hooks/useKite';

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

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  th: { textAlign: 'left' as const, color: t.dim, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', fontSize: 12, color: t.bright, borderBottom: `1px solid ${tint(t.border, 50)}` },
  hint: { color: t.dim, fontSize: 11 },
  inSm: { background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: '3px 6px', fontFamily: 'inherit', fontSize: 11 },
  pill: { padding: '1px 6px', borderRadius: 999, fontSize: 9, fontWeight: 700, border: `1px solid ${t.border}`, color: t.dim },
};

const num = (v: any) => Number(v ?? 0);
const pnlColor = (v: number) => (v > 0 ? t.green : v < 0 ? t.red : t.dim);

function ConvertControl({ p }: { p: any }) {
  const convert = useConvertKitePosition();
  const products = ['MIS', 'CNC', 'NRML'].filter((x) => x !== p.product);
  const [target, setTarget] = useState(products[0]);
  if (!num(p.quantity)) return null;
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', justifyContent: 'flex-end' }}>
      <select style={S.inSm} value={target} onChange={(e) => setTarget(e.target.value)}>
        {products.map((x) => <option key={x} value={x}>{x}</option>)}
      </select>
      <span
        style={{ cursor: 'pointer', color: convert.isError ? t.red : t.blue, fontSize: 11 }}
        title={convert.isError ? (convert.error as Error).message : `Convert ${p.product} → ${target}`}
        onClick={() => convert.mutate({
          tradingsymbol: p.tradingsymbol, exchange: p.exchange,
          transaction_type: num(p.quantity) >= 0 ? 'BUY' : 'SELL', position_type: 'day',
          quantity: Math.abs(num(p.quantity)), old_product: p.product, new_product: target,
        })}
      >
        {convert.isPending ? '…' : convert.isSuccess ? '✓' : 'convert'}
      </span>
    </div>
  );
}

function AuthoriseHoldingsButton() {
  const authorise = useInitiateHoldingsAuth();
  return (
    <button
      style={{ background: tint(t.blue, 12), color: t.blue, border: `1px solid ${t.blue}`, borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
      title="Authorise holdings via CDSL TPIN (eDIS) — required to sell delivery holdings through the API"
      disabled={authorise.isPending}
      onClick={() => authorise.mutate({}, {
        onSuccess: (res) => { if (res.authorise_url) window.open(res.authorise_url, '_blank', 'noopener'); },
      })}
    >
      {authorise.isPending ? 'Authorising…' : 'Authorise holdings (eDIS)'}
    </button>
  );
}

function AuctionsSection() {
  const { data: auctions } = useKiteAuctions(true);
  if (!auctions || auctions.length === 0) return null;
  return (
    <div style={{ marginTop: 48 }}>
      <h2 style={{ fontSize: 18, fontWeight: 400, color: t.bright, marginBottom: 24 }}>
        Auctions <span style={{ color: t.dim, fontSize: 14 }}>({auctions.length})</span>
      </h2>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
        <thead><tr>
          <th style={S.th}>Instrument</th>
          <th style={S.th}>Auction #</th>
          <th style={{ ...S.th, textAlign: 'right' }}>Qty.</th>
          <th style={{ ...S.th, textAlign: 'right' }}>Last price</th>
        </tr></thead>
        <tbody>
          {auctions.map((a: any, i: number) => (
            <tr key={`${a.tradingsymbol}-${i}`}>
              <td style={S.td}>
                <span style={{ color: t.bright, marginRight: 8 }}>{a.tradingsymbol}</span>
                <span style={{ fontSize: 9, color: t.dim, padding: '1px 4px', background: t.surface, borderRadius: 2 }}>{a.exchange}</span>
              </td>
              <td style={{ ...S.td, color: t.dim }}>{a.auction_number}</td>
              <td style={{ ...S.td, textAlign: 'right' }}>{num(a.quantity)}</td>
              <td style={{ ...S.td, textAlign: 'right' }}>{num(a.last_price).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ ...S.hint, marginTop: 8 }}>Shares from settlement shortfalls that are eligible for the exchange auction window.</div>
    </div>
  );
}

export function PortfolioPane({ view }: { view?: 'holdings' | 'positions' }) {
  const { data: holdings } = useKiteHoldings(true);
  const { data: pos } = useKitePositions(true);
  const positions = (pos?.net ?? []).filter((p: any) => num(p.quantity) !== 0 || num(p.pnl) !== 0);

  const showHoldings = view === 'holdings' || !view;
  const showPositions = view === 'positions' || !view;

  const [selectedPos, setSelectedPos] = useState<Set<string>>(new Set());

  const togglePos = (id: string) => {
    const next = new Set(selectedPos);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedPos(next);
  };

  const toggleAllPos = () => {
    if (selectedPos.size === positions.length && positions.length > 0) setSelectedPos(new Set());
    else setSelectedPos(new Set(positions.map((p: any) => `${p.exchange}:${p.tradingsymbol}`)));
  };

  const totalPosPnl = positions.reduce((acc: number, p: any) => acc + num(p.pnl), 0);
  const totalHoldingsPnl = (holdings || []).reduce((acc: number, h: any) => acc + num(h.pnl), 0);
  const totalHoldingsVal = (holdings || []).reduce((acc: number, h: any) => acc + (num(h.quantity) * num(h.last_price)), 0);

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 32px' }}>
      {showPositions && (
        <div style={{ marginBottom: 48 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <h2 style={{ fontSize: 18, fontWeight: 400, color: t.bright, margin: 0 }}>
              Positions <span style={{ color: t.dim, fontSize: 14 }}>({positions.length})</span>
            </h2>
          </div>
          {positions.length === 0 && <div style={S.hint}>No open positions.</div>}
          {positions.length > 0 && (
            <div style={{ position: 'relative' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead><tr>
                  <th style={{ ...S.th, width: 40, textAlign: 'center' }}>
                    <input type="checkbox" checked={selectedPos.size === positions.length && positions.length > 0} onChange={toggleAllPos} style={{ cursor: 'pointer' }} />
                  </th>
                  <th style={S.th}>Product</th>
                  <th style={S.th}>Instrument</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>Qty.</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>Avg.</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>LTP</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>P&L</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>Chg.</th>
                </tr></thead>
                <tbody>
                  {positions.map((p: any, idx: number) => {
                    const qty = num(p.quantity);
                    const id = `${p.exchange}:${p.tradingsymbol}`;
                    const isSelected = selectedPos.has(id);
                    const chg = ((num(p.last_price) - num(p.average_price)) / (num(p.average_price) || 1)) * 100;
                    return (
                      <tr key={`${id}-${idx}`} style={{ background: isSelected ? tint(t.blue, 5) : 'transparent' }}>
                        <td style={{ ...S.td, textAlign: 'center' }}>
                          <input type="checkbox" checked={isSelected} onChange={() => togglePos(id)} style={{ cursor: 'pointer' }} />
                        </td>
                        <td style={S.td}><span style={{ ...S.pill, background: t.surface, color: t.dim, border: 'none', padding: '2px 6px', fontSize: 10 }}>{p.product}</span></td>
                        <td style={S.td}>
                          <span style={{ color: t.bright, marginRight: 8 }}>{parseTs(p.tradingsymbol)}</span>
                          <span style={{ fontSize: 9, color: t.dim, padding: '1px 4px', background: t.surface, borderRadius: 2 }}>{p.exchange}</span>
                        </td>
                        <td style={{ ...S.td, textAlign: 'right', color: qty >= 0 ? t.blue : t.red }}>{qty}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(p.average_price).toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(p.last_price).toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right', color: pnlColor(num(p.pnl)) }}>{num(p.pnl).toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right', color: pnlColor(chg) }}>{chg.toFixed(2)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 8px', borderBottom: `1px solid ${tint(t.border, 50)}`, background: t.bg }}>
                <div style={{ minWidth: 150 }}>
                  {selectedPos.size > 0 && (
                    <button style={{ background: '#4184f3', color: '#fff', border: 'none', borderRadius: 4, padding: '8px 16px', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}>
                      Exit {selectedPos.size} position(s)
                    </button>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 32, fontSize: 14 }}>
                  <div>
                    <span style={{ color: t.dim, marginRight: 8 }}>Day's P&L</span>
                    <span style={{ color: pnlColor(totalPosPnl), fontWeight: 500 }}>{totalPosPnl.toFixed(2)}</span>
                  </div>
                  <div>
                    <span style={{ color: t.dim, marginRight: 8 }}>Total P&L</span>
                    <span style={{ color: pnlColor(totalPosPnl), fontWeight: 500 }}>{totalPosPnl.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {showHoldings && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <h2 style={{ fontSize: 18, fontWeight: 400, color: t.bright, margin: 0 }}>
              Holdings <span style={{ color: t.dim, fontSize: 14 }}>({holdings?.length || 0})</span>
            </h2>
            <AuthoriseHoldingsButton />
          </div>
          {(!holdings || holdings.length === 0) && <div style={S.hint}>No equity holdings.</div>}
          {holdings && holdings.length > 0 && (
            <div>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead><tr>
                  <th style={S.th}>Instrument</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>Qty.</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>Avg. cost</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>LTP</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>Cur. val</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>P&L</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>Net chg.</th>
                  <th style={{ ...S.th, textAlign: 'right' }}>Day chg.</th>
                </tr></thead>
                <tbody>
                  {holdings.map((h: any, idx: number) => {
                    const pnl = num(h.pnl);
                    const curVal = num(h.quantity) * num(h.last_price);
                    const netChg = ((num(h.last_price) - num(h.average_price)) / (num(h.average_price) || 1)) * 100;
                    return (
                      <tr key={`${h.tradingsymbol}-${idx}`}>
                        <td style={S.td}>
                          <span style={{ color: t.bright, marginRight: 8 }}>{parseTs(h.tradingsymbol)}</span>
                          <span style={{ fontSize: 9, color: t.dim, padding: '1px 4px', background: t.surface, borderRadius: 2 }}>{h.exchange}</span>
                        </td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(h.quantity)}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(h.average_price).toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(h.last_price).toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{curVal.toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right', color: pnlColor(pnl) }}>{pnl.toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right', color: pnlColor(netChg) }}>{netChg.toFixed(2)}%</td>
                        <td style={{ ...S.td, textAlign: 'right', color: t.dim }}>0.00%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', padding: '16px 8px', borderBottom: `1px solid ${tint(t.border, 50)}`, background: t.bg }}>
                <div style={{ display: 'flex', gap: 32, fontSize: 14 }}>
                  <div>
                    <span style={{ color: t.dim, marginRight: 8 }}>Total investment</span>
                    <span style={{ color: t.bright, fontWeight: 500 }}>{(totalHoldingsVal - totalHoldingsPnl).toFixed(2)}</span>
                  </div>
                  <div>
                    <span style={{ color: t.dim, marginRight: 8 }}>Current value</span>
                    <span style={{ color: t.bright, fontWeight: 500 }}>{totalHoldingsVal.toFixed(2)}</span>
                  </div>
                  <div>
                    <span style={{ color: t.dim, marginRight: 8 }}>Day's P&L</span>
                    <span style={{ color: pnlColor(totalHoldingsPnl), fontWeight: 500 }}>{totalHoldingsPnl.toFixed(2)}</span>
                  </div>
                  <div>
                    <span style={{ color: t.dim, marginRight: 8 }}>Total P&L</span>
                    <span style={{ color: pnlColor(totalHoldingsPnl), fontWeight: 500 }}>{totalHoldingsPnl.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          <AuctionsSection />
        </div>
      )}
    </div>
  );
}
