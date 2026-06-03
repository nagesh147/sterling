import React from 'react';
import { card, cardHead, cardBody, c, alpha } from '../../styles/terminalUI';
import { useV2Signals, V2Signal } from '../../hooks/useSterlingV2';

const fmt = (v: number | null | undefined, d = 2): string =>
  v == null || !isFinite(v) ? '—' : v.toLocaleString('en-US', { maximumFractionDigits: d });

function sideLabel(side: number): { txt: string; color: string } {
  if (side === 1) return { txt: 'LONG', color: c.green };
  if (side === -1) return { txt: 'SHORT', color: c.red };
  return { txt: 'FLAT', color: c.dim };
}

const th: React.CSSProperties = {
  textAlign: 'right', padding: '6px 10px', fontSize: 9, fontWeight: 600,
  letterSpacing: '0.06em', color: c.dim, textTransform: 'uppercase',
  borderBottom: `1px solid ${c.border}`, whiteSpace: 'nowrap',
};
const td: React.CSSProperties = {
  textAlign: 'right', padding: '7px 10px', fontSize: 11, color: c.bright,
  fontVariantNumeric: 'tabular-nums', borderBottom: `1px solid ${alpha(c.border, 0.5)}`,
};

export function V2SignalsPane({ active }: { active: boolean }) {
  const { data, isLoading, error } = useV2Signals(active);

  return (
    <div style={card}>
      <div style={cardHead}>
        <span>V2 LIVE SIGNALS</span>
        <span style={{
          marginLeft: 'auto', fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
          color: c.amber, border: `1px solid ${alpha(c.amber, 0.5)}`,
          background: alpha(c.amber, 0.12), padding: '2px 7px', borderRadius: 4,
        }}>
          PAPER · AUTO-EXEC OFF
        </span>
      </div>
      <div style={cardBody}>
        {isLoading && <div style={{ color: c.dim, fontSize: 12 }}>Loading latest bars…</div>}
        {error && <div style={{ color: c.red, fontSize: 12 }}>{String((error as Error).message)}</div>}
        {data && (
          <>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ ...th, textAlign: 'left' }}>Symbol</th>
                  <th style={{ ...th, textAlign: 'left' }}>Side</th>
                  <th style={th}>Entry</th>
                  <th style={th}>Stop</th>
                  <th style={th}>Target</th>
                  <th style={th}>ADX</th>
                  <th style={{ ...th, textAlign: 'left' }}>Bar (UTC)</th>
                </tr>
              </thead>
              <tbody>
                {data.signals.map((s: V2Signal) => {
                  const sl = sideLabel(s.side);
                  return (
                    <tr key={s.symbol}>
                      <td style={{ ...td, textAlign: 'left', fontWeight: 700 }}>{s.symbol}</td>
                      <td style={{ ...td, textAlign: 'left' }}>
                        <span style={{ color: sl.color, fontWeight: 700 }}>{sl.txt}</span>
                      </td>
                      <td style={td}>{fmt(s.entry)}</td>
                      <td style={{ ...td, color: s.stop == null ? c.dim : c.red }}>{fmt(s.stop)}</td>
                      <td style={{ ...td, color: s.target == null ? c.dim : c.green }}>{fmt(s.target)}</td>
                      <td style={{ ...td, color: s.conviction >= 25 ? c.green : c.dim }}>{fmt(s.conviction, 1)}</td>
                      <td style={{ ...td, textAlign: 'left', color: c.dim, fontSize: 10 }}>{s.bar_time}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div style={{ color: c.dim, fontSize: 10, marginTop: 10, lineHeight: 1.5 }}>
              {data.signals[0]?.strategy} @ {data.signals[0]?.tf} · long+short + vol-sizing stack.
              Display only — no order is ever placed automatically.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
