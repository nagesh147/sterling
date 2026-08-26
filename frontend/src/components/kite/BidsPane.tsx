import React, { useState } from 'react';
import { useKiteAuctions, useKiteIPOs, useKiteCorporateActions } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';
import { k } from '../../styles/kiteUI';

const S: Record<string, React.CSSProperties> = {
  container: { padding: '24px 32px', width: '100%', height: '100%', display: 'flex', flexDirection: 'column' as const, fontFamily: k.fontFamily },
  title: { fontSize: 24, fontWeight: 400, color: 'var(--k-text)', margin: '0 0 24px 0' },
  navContainer: { display: 'flex', gap: 32, borderBottom: `1px solid var(--k-surface-hover)`, marginBottom: 24 },
  navItem: { padding: '0 0 12px 0', fontSize: 14, cursor: 'pointer', transition: 'color 0.2s' },
  content: { color: 'var(--k-dim)', fontSize: 13, lineHeight: '1.5' },
  hint: { color: 'var(--k-dim)', fontSize: 13 },
  th: { padding: '12px 0', textAlign: 'left', color: 'var(--k-dim)', fontSize: 12, fontWeight: 400, borderBottom: `1px solid var(--k-surface-hover)` },
  td: { padding: '12px 0', color: 'var(--k-text)', fontSize: 13, borderBottom: `1px solid var(--k-surface-hover)` },
  emptyContainer: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '64px 0', color: 'var(--k-dim)' },
  emptyTitle: { fontSize: 16, color: 'var(--k-dim)', marginBottom: 8, marginTop: 24 },
  emptyText: { fontSize: 14, marginBottom: 16 },
  link: { color: 'var(--k-blue-kite)', textDecoration: 'none' }
};

const EmptySvg = () => (
  <svg width="84" height="84" viewBox="0 0 24 24" fill="none">
    <rect x="5" y="3" width="14" height="18" rx="1" fill="var(--k-surface-hover)" stroke="var(--k-border-strong)" strokeWidth="1" />
    <path d="M5 6h2M5 10h2M5 14h2M5 18h2" stroke="var(--k-border-strong)" strokeWidth="1" />
    <rect x="9" y="7" width="6" height="1" fill="var(--k-border-strong)" />
    <rect x="9" y="11" width="8" height="1" fill="var(--k-border-strong)" />
    <rect x="9" y="15" width="7" height="1" fill="var(--k-border-strong)" />
  </svg>
);

export function BidsPane() {
  const [tab, setTab] = useState<'ipo' | 'gsec' | 'auctions' | 'corporate_actions' | 'sse_ipo'>('ipo');
  
  const { data: auctions, isLoading: isLoadingAuctions } = useKiteAuctions(tab === 'auctions');
  const { data: iposData, isLoading: isLoadingIpos } = useKiteIPOs(tab === 'ipo');
  const { data: corpActions, isLoading: isLoadingCorp } = useKiteCorporateActions(tab === 'corporate_actions');
  
  const tabs = [
    { id: 'ipo', label: 'IPO' },
    { id: 'gsec', label: 'Govt. securities' },
    { id: 'auctions', label: 'Auctions' },
    { id: 'corporate_actions', label: 'Corporate actions' },
    { id: 'sse_ipo', label: 'SSE IPO' }
  ] as const;

  const ipos = iposData || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--k-bg)', color: 'var(--k-text)' }}>
      <div style={{ padding: '0 32px', borderBottom: '1px solid var(--k-surface-hover)', marginTop: 12 }}>
        <h2 style={{ fontSize: 24, fontWeight: 400, color: 'var(--k-text)', margin: '0 0 24px 0' }}>Bids</h2>
        <div style={{ display: 'flex', gap: 32, marginBottom: -1 }}>
          {tabs.map(tItem => (
            <div
              key={tItem.id}
              onClick={() => setTab(tItem.id as any)}
              style={{
                ...S.navItem,
                color: tab === tItem.id ? 'var(--k-orange)' : 'var(--k-text)',
                borderBottom: tab === tItem.id ? '2px solid var(--k-orange)' : '2px solid transparent',
                fontWeight: 400
              }}
            >
              {tItem.label}
            </div>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>

      <div style={S.content}>
        {tab === 'auctions' && (
          <div>
            {isLoadingAuctions ? <div style={S.hint}>Loading auctions...</div> : (!auctions || auctions.length === 0) ? (
              <div style={S.emptyContainer}>
                <EmptySvg />
                <div style={S.emptyTitle}>No securities available for bidding currently.</div>
                <div style={S.emptyText}><a href="#" style={S.link}>Learn more</a></div>
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={S.th}>Instrument</th>
                    <th style={S.th}>Qty.</th>
                    <th style={S.th}>Price</th>
                    <th style={{...S.th, textAlign: 'right'}}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {auctions.map((a: any, i: number) => (
                    <tr key={i} style={{ borderBottom: `1px solid var(--k-surface-hover)` }}>
                      <td style={S.td}><InstrumentLabel symbol={a.tradingsymbol} /></td>
                      <td style={S.td}>{a.quantity}</td>
                      <td style={S.td}>{a.price}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{a.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {tab === 'ipo' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <div style={{ color: 'var(--k-dim)', fontSize: 14 }}>IPOs ({ipos.length})</div>
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--k-dim)', fontSize: 12 }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                </span>
                <input type="text" placeholder="Search" style={{ padding: '6px 8px 6px 28px', border: `1px solid var(--k-surface-hover)`, borderRadius: 3, background: 'transparent', color: 'var(--k-text)', fontSize: 12, width: 150, outline: 'none' }} />
              </div>
            </div>
            {isLoadingIpos ? <div style={S.hint}>Loading IPOs...</div> : ipos.length === 0 ? <div style={S.hint}>There are no active IPO applications.</div> : (
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr>
                  <th style={{...S.th, width: '35%'}}>Instrument</th>
                  <th style={{...S.th, width: '20%'}}>Date</th>
                  <th style={{...S.th, width: '15%'}}>Price (₹)</th>
                  <th style={{...S.th, width: '20%'}}>Min. amount (₹)</th>
                  <th style={{...S.th, width: '10%'}}></th>
                </tr>
              </thead>
              <tbody>
                {ipos.map((a, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid var(--k-surface-hover)` }}>
                    <td style={{ padding: '16px 0' }}>
                      <div style={{ color: 'var(--k-text)', fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{a.symbol}</div>
                      <div style={{ color: 'var(--k-dim)', fontSize: 11 }}>{a.name}</div>
                    </td>
                    <td style={{ padding: '16px 0', color: 'var(--k-text)' }}>{a.dates}</td>
                    <td style={{ padding: '16px 0', color: 'var(--k-text)' }}>{a.price}</td>
                    <td style={{ padding: '16px 0', color: 'var(--k-text)' }}>
                      <div style={{ color: 'var(--k-text)', fontSize: 13, marginBottom: 4 }}>{a.minAmount}</div>
                      <div style={{ color: 'var(--k-dim)', fontSize: 11 }}>{a.qty}</div>
                    </td>
                    <td style={{ padding: '16px 0', textAlign: 'right' }}>
                      {a.status === 'Apply' ? (
                        <button style={{ padding: '6px 16px', background: 'var(--k-blue-kite)', color: 'var(--k-on-accent)', border: 'none', borderRadius: 3, cursor: 'pointer', fontSize: 13, fontWeight: 500 }}>Apply</button>
                      ) : (
                        <span style={{ color: 'var(--k-dim)', fontSize: 13, padding: '4px 8px' }}>closed</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            )}
            <div style={{ marginTop: 24, textAlign: 'center', fontSize: 13, color: 'var(--k-dim)' }}>
              Don't see an IPO here? <a href="#" style={S.link}>View upcoming →</a>
            </div>
          </div>
        )}
        
        {tab === 'gsec' && (
          <div>
            <div style={S.emptyContainer}>
              <EmptySvg />
              <div style={S.emptyTitle}>No securities available for bidding currently.</div>
              <div style={S.emptyText}><a href="#" style={S.link}>Learn more</a></div>
            </div>
          </div>
        )}

        {tab === 'corporate_actions' && (
          <div>
            {isLoadingCorp ? <div style={S.hint}>Loading corporate actions...</div> : (!corpActions || corpActions.length === 0) ? (
              <div style={S.emptyContainer}>
                <EmptySvg />
                <div style={S.emptyTitle}>No corporate actions currently available.</div>
                <div style={S.emptyText}><a href="#" style={S.link}>Learn more</a></div>
              </div>
            ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr>
                  <th style={{...S.th, width: '25%'}}>Company</th>
                  <th style={{...S.th, width: '25%'}}>Starts at</th>
                  <th style={{...S.th, width: '25%'}}>Ends on</th>
                  <th style={{...S.th, width: '15%'}}>Offer price</th>
                  <th style={{...S.th, width: '10%'}}></th>
                </tr>
              </thead>
              <tbody>
                {corpActions.map((a: any, i: number) => (
                  <tr key={i} style={{ borderBottom: `1px solid var(--k-surface-hover)` }}>
                    <td style={{ padding: '16px 0' }}>
                      <span style={{ 
                        display: 'inline-block', 
                        padding: '2px 6px', 
                        borderRadius: 3, 
                        fontSize: 10, 
                        fontWeight: 500, 
                        marginBottom: 6,
                        background: a.type === 'BUYBACK' ? 'rgba(229, 115, 115, 0.15)' : 'rgba(56, 126, 209, 0.15)',
                        color: a.type === 'BUYBACK' ? '#e57373' : 'var(--k-blue-kite)',
                      }}>
                        {a.type}
                      </span>
                      <div style={{ color: 'var(--k-text)', fontSize: 13, fontWeight: 500 }}>{a.symbol}</div>
                    </td>
                    <td style={{ padding: '16px 0', color: 'var(--k-text)' }}>{a.startsAt}</td>
                    <td style={{ padding: '16px 0', color: 'var(--k-text)' }}>{a.endsOn}</td>
                    <td style={{ padding: '16px 0', color: 'var(--k-text)' }}>₹ {a.offerPrice}</td>
                    <td style={{ padding: '16px 0', textAlign: 'right' }}>
                      <a href="#" style={{ ...S.link, fontSize: 13 }}>Place order</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            )}
          </div>
        )}
        
        {tab === 'sse_ipo' && (
          <div>
            <div style={S.emptyContainer}>
              <EmptySvg />
              <div style={S.emptyTitle}>No active Social Stock Exchange (SSE) issues.</div>
              <div style={S.emptyText}>SSE allows non-profits to raise funds for their causes. <a href="#" style={S.link}>Learn more</a></div>
            </div>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
