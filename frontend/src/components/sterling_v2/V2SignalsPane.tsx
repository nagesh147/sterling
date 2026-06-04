import React, { useState } from 'react';
import { card, cardHead, cardBody, alpha, c } from '../../styles/terminalUI';
import { useV2Signals, V2Signal } from '../../hooks/useSterlingV2';

const fmtUsd = (v: number | null | undefined): string => v == null || !isFinite(v) ? '—' : '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 });
const fmtTime = (ms: number | null | undefined) => !ms ? '—' : new Date(ms).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
const fmt = (v: number | null | undefined, d = 2): string => v == null || !isFinite(v) ? '—' : v.toFixed(d);

function SectionCard({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={card}>
      <div style={cardHead}><span>{title}</span>{right && <span style={{ marginLeft: 'auto' }}>{right}</span>}</div>
      <div style={cardBody}>{children}</div>
    </div>
  );
}

function V2SignalTable({ title, signals, instrumentType }: { title: string, signals: V2Signal[], instrumentType: 'spot' | 'futures' | 'options' }) {
  const [expanded, setExpanded] = useState<string>('');

  const headers = instrumentType === 'spot'
    ? ['Symbol', 'ID', 'Time', 'Status', 'Direction', 'Entry', 'Current', 'Dyn SL', 'Target', 'Margin', 'Risk', 'Strategy', 'Type', '']
    : instrumentType === 'futures'
    ? ['Symbol', 'ID', 'Time', 'Status', 'Direction', 'Entry', 'Current', 'Dyn SL', 'Target', 'Lev', 'Margin', 'Risk', 'Strategy', 'Type', '']
    : ['Symbol', 'ID', 'Time', 'Status', 'Direction', 'Entry', 'Current', 'Strike', 'Premium', 'Max Loss', 'Breakeven', 'Expiry', 'Strategy', 'Type', ''];

  return (
    <SectionCard 
      title={title} 
      right={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
            color: c.amber, border: `1px solid ${alpha(c.amber, 0.5)}`,
            background: alpha(c.amber, 0.12), padding: '3px 9px', borderRadius: 4,
          }}>
            PAPER · AUTO-EXEC OFF
          </span>
        </div>
      }
    >
      <table style={{ width: '100%', minWidth: 920, tableLayout: 'fixed', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead>
          <tr style={{ background: c.surface, color: c.muted, fontSize: 9, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            {headers.map((h, i) => (
              <th key={i} style={{ padding: '5px 8px', textAlign: i >= headers.length - 2 ? 'right' : 'left', borderBottom: `1px solid ${c.border}`, whiteSpace: 'nowrap' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {signals.map((s: V2Signal, idx: number) => {
            const sigIdStr = `${s.underlying || s.symbol}-${s.direction || s.side}-${s.instrument_type}`;
            const sigIdHash = Array.from(sigIdStr).reduce((h, ch) => Math.imul(31, h) + ch.charCodeAt(0) | 0, 0);
            const sigId = Math.abs(sigIdHash).toString(16).substring(0, 5).toUpperCase() + `-${idx}`;
            
            const isExp = expanded === sigId;
            const long = s.direction === 'long' || s.side === 1;
            const short = s.direction === 'short' || s.side === -1;
            const dirColor = long ? 'var(--t-green)' : short ? 'var(--t-red)' : 'var(--t-dim)';
            
            const hasPlan = long || short;
            const statusColor = hasPlan ? dirColor : 'var(--t-dim)';
            const statusLabel = hasPlan ? 'READY' : 'IDLE';

            return (
              <React.Fragment key={sigId}>
                <tr onClick={() => setExpanded(isExp ? '' : sigId)} style={{ cursor: 'pointer', borderBottom: isExp ? 'none' : `1px solid ${c.border2}`, background: isExp ? alpha(statusColor, 0.09) : undefined }}>
                  <td style={{ padding: '5px 8px', fontWeight: 700, color: 'var(--t-bright)' }}>
                    <span style={{ color: dirColor }}>{long ? '▲' : short ? '▼' : '–'}</span> {s.underlying || s.symbol}
                    {s.recommended && hasPlan && <span style={{ marginLeft: 6, fontSize: 8, background: alpha('var(--t-amber)', 0.15), border: '1px solid ' + alpha('var(--t-amber)', 0.4), color: 'var(--t-amber)', padding: '2px 4px', borderRadius: 3, verticalAlign: 'middle' }}>★ BEST</span>}
                  </td>
                  <td style={{ padding: '5px 8px', fontSize: 9, color: 'var(--t-dim)', fontFamily: 'monospace' }}>{sigId}</td>
                  <td style={{ padding: '5px 8px' }}>{fmtTime(s.timestamp_ms)}</td>
                  <td style={{ padding: '5px 8px', fontWeight: 700, color: statusColor, fontSize: 10, letterSpacing: '0.06em' }}>{statusLabel}</td>
                  <td style={{ padding: '5px 8px', fontWeight: 600, color: dirColor }}>{long ? '▲ LONG' : short ? '▼ SHORT' : '—'}</td>
                  <td style={{ padding: '5px 8px' }}>{hasPlan ? fmtUsd(s.entry) : '—'}</td>
                  <td style={{ padding: '5px 8px', color: 'var(--t-bright)' }}>{fmtUsd(s.current_price || s.entry)}</td>
                  
                  {instrumentType === 'spot' && (
                    <>
                      <td style={{ padding: '5px 8px', color: 'var(--t-red)' }}>{hasPlan ? fmtUsd(s.stop) : '—'}</td>
                      <td style={{ padding: '5px 8px', color: 'var(--t-amber)' }}>{hasPlan ? fmtUsd(s.target) : '—'}</td>
                      <td style={{ padding: '5px 8px', fontWeight: 600, color: 'var(--t-dim)' }}>{hasPlan && s.margin ? fmtUsd(s.margin) : '—'}</td>
                      <td style={{ padding: '5px 8px', fontFamily: 'monospace', color: 'var(--t-text)' }}>
                        {hasPlan && s.risk_pct ? `${fmt(s.risk_pct * 100)}%` : '—'}
                      </td>
                    </>
                  )}

                  {instrumentType === 'futures' && (
                    <>
                      <td style={{ padding: '5px 8px', color: 'var(--t-red)' }}>{hasPlan ? fmtUsd(s.stop) : '—'}</td>
                      <td style={{ padding: '5px 8px', color: 'var(--t-amber)' }}>{hasPlan ? fmtUsd(s.target) : '—'}</td>
                      <td style={{ padding: '5px 8px', fontWeight: 600, color: 'var(--t-blue)' }}>{hasPlan && s.leverage ? `${s.leverage}x` : '—'}</td>
                      <td style={{ padding: '5px 8px', fontWeight: 600, color: 'var(--t-dim)' }}>{hasPlan && s.margin ? fmtUsd(s.margin) : '—'}</td>
                      <td style={{ padding: '5px 8px', fontFamily: 'monospace', color: 'var(--t-text)' }}>
                        {hasPlan && s.risk_pct ? `${fmt(s.risk_pct * 100)}%` : '—'}
                      </td>
                    </>
                  )}

                  {instrumentType === 'options' && (
                    <>
                      <td style={{ padding: '5px 8px', color: 'var(--t-purple)', fontWeight: 600 }}>{hasPlan && s.strike ? fmtUsd(s.strike) : '—'}</td>
                      <td style={{ padding: '5px 8px', color: 'var(--t-amber)' }}>{hasPlan && s.premium ? fmtUsd(s.premium) : '—'}</td>
                      <td style={{ padding: '5px 8px', color: 'var(--t-red)' }}>{hasPlan && s.max_loss ? fmtUsd(s.max_loss) : '—'}</td>
                      <td style={{ padding: '5px 8px', fontFamily: 'monospace', color: 'var(--t-text)' }}>
                        {hasPlan && s.breakeven_pct ? `${fmt(s.breakeven_pct * 100)}%` : '—'}
                      </td>
                      <td style={{ padding: '5px 8px', color: 'var(--t-dim)' }}>{hasPlan && s.expiry_days ? `${fmt(s.expiry_days, 1)}d` : '—'}</td>
                    </>
                  )}

                  <td style={{ padding: '5px 8px', textTransform: 'uppercase', fontSize: 9 }}>
                    {s.strategy ? s.strategy.replace(/_/g, ' ') : '—'}
                  </td>
                  <td style={{ padding: '5px 8px', textAlign: 'right' }}>
                    {hasPlan ? (
                      <span style={{ display: 'inline-block', width: 105, boxSizing: 'border-box', textAlign: 'center', fontSize: 10, fontWeight: 700, padding: '4px 8px', borderRadius: 4, background: alpha('var(--t-blue)', 0.1), color: 'var(--t-blue)', whiteSpace: 'nowrap' }}>V2 PAPER</span>
                    ) : null}
                  </td>
                  <td style={{ padding: '5px 8px' }} />
                </tr>
                {isExp && (
                  <tr style={{ background: alpha(statusColor, 0.04), borderBottom: `1px solid ${c.border2}` }}>
                    <td colSpan={headers.length} style={{ padding: '12px 14px' }}>
                      <div style={{ fontSize: 11, color: 'var(--t-text)' }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 18px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 60 }}>
                            <span style={{ fontSize: 9, letterSpacing: '0.07em', color: 'var(--t-dim)', fontWeight: 600, textTransform: 'uppercase' }}>Profile</span>
                            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--t-bright)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{s.profile || 'SCALPING'}</span>
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 60 }}>
                            <span style={{ fontSize: 9, letterSpacing: '0.07em', color: 'var(--t-dim)', fontWeight: 600, textTransform: 'uppercase' }}>Pattern</span>
                            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--t-amber)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{s.strategy ? s.strategy.replace(/_/g, ' ') : '—'}</span>
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 60 }}>
                            <span style={{ fontSize: 9, letterSpacing: '0.07em', color: 'var(--t-dim)', fontWeight: 600, textTransform: 'uppercase' }}>TF</span>
                            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--t-bright)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{s.tf}</span>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </SectionCard>
  );
}

export function V2SignalsPane({ active }: { active: boolean }) {
  const { data, isLoading, error } = useV2Signals(active);
  const [profile, setProfile] = useState<string>('ALL');

  const signals = data?.signals || [];

  // Distinct profiles present in the feed, for the user-facing selector.
  const profiles = React.useMemo(
    () => Array.from(new Set(signals.map(s => s.profile).filter(Boolean) as string[])).sort(),
    [signals]
  );

  // Reset to ALL if a previously-selected profile is no longer in the feed.
  React.useEffect(() => {
    if (profile !== 'ALL' && profiles.length && !profiles.includes(profile)) setProfile('ALL');
  }, [profile, profiles]);

  const shown = profile === 'ALL' ? signals : signals.filter(s => s.profile === profile);
  const spotSignals = shown.filter(s => s.instrument_type === 'spot');
  const futuresSignals = shown.filter(s => s.instrument_type === 'futures');
  const optionsSignals = shown.filter(s => s.instrument_type === 'options');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
      {isLoading && <div style={{ color: c.dim, fontSize: 12, padding: 16 }}>Loading latest bars…</div>}
      {error && <div style={{ color: c.red, fontSize: 12, padding: 16 }}>{String((error as Error).message)}</div>}
      {data && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '2px 2px 12px' }}>
            <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', color: c.muted, textTransform: 'uppercase' }}>Profile</span>
            <select
              value={profile}
              onChange={(e) => setProfile(e.target.value)}
              style={{
                fontSize: 11, fontWeight: 600, color: c.text, background: c.surface,
                border: `1px solid ${c.border}`, borderRadius: 4, padding: '4px 10px',
                cursor: 'pointer', outline: 'none', letterSpacing: '0.03em',
              }}
            >
              <option value="ALL">All Profiles</option>
              {profiles.map(p => <option key={p} value={p}>{p.replace(/_/g, ' ')}</option>)}
            </select>
            <span style={{ fontSize: 9, color: c.dim, marginLeft: 'auto' }}>
              {spotSignals.length} setup{spotSignals.length === 1 ? '' : 's'}
              {profile !== 'ALL' ? ` · ${profile.replace(/_/g, ' ')}` : ''}
            </span>
          </div>
          <V2SignalTable title="V2 ENGINE · SPOT" signals={spotSignals} instrumentType="spot" />
          <div style={{ height: 16 }} />
          <V2SignalTable title="V2 ENGINE · FUTURES" signals={futuresSignals} instrumentType="futures" />
          <div style={{ height: 16 }} />
          <V2SignalTable title="V2 ENGINE · OPTIONS" signals={optionsSignals} instrumentType="options" />
        </>
      )}
      
      <div style={{ height: 32 }} />
    </div>
  );
}
