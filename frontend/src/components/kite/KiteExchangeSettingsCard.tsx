import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  DEFAULT_KITE_EXCHANGES,
  KITE_EXCHANGES,
  readKiteExchanges,
  writeKiteExchanges,
  type KiteExchange,
} from '../../utils/kiteExchanges';

const ORANGE = '#f06428';

export function KiteExchangeSettingsCard() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = React.useState<KiteExchange[]>(() => readKiteExchanges());

  const apply = (next: readonly string[]) => {
    const saved = writeKiteExchanges(next);
    setSelected(saved);
    void queryClient.invalidateQueries({ queryKey: ['kite-instruments'] });
    void queryClient.invalidateQueries({ queryKey: ['kite-engine-signals'] });
    void queryClient.invalidateQueries({ queryKey: ['kite-engine-open-positions'] });
    window.dispatchEvent(new CustomEvent('kite-exchanges-changed', { detail: saved }));
  };

  const toggle = (exchange: KiteExchange) => {
    const next = selected.includes(exchange)
      ? selected.filter((item) => item !== exchange)
      : [...selected, exchange];
    apply(next.length ? next : DEFAULT_KITE_EXCHANGES);
  };

  const isDefault = selected.length === DEFAULT_KITE_EXCHANGES.length
    && DEFAULT_KITE_EXCHANGES.every((exchange) => selected.includes(exchange));
  const isAll = selected.length === KITE_EXCHANGES.length;

  const presetStyle = (active: boolean): React.CSSProperties => ({
    minHeight: 32,
    border: 'none',
    borderRadius: 6,
    background: active ? '#fff' : 'transparent',
    color: active ? '#444' : '#777',
    boxShadow: active ? `inset 0 -2px ${ORANGE}, 0 1px 2px rgba(0,0,0,.08)` : 'none',
    padding: '0 13px',
    fontSize: 11,
    fontWeight: active ? 700 : 550,
    cursor: 'pointer',
    fontFamily: 'inherit',
  });

  return (
    <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: 9, padding: 18, marginBottom: 16, boxShadow: '0 1px 2px rgba(0,0,0,.025)' }}>
      <div style={{ color: '#777', fontSize: 10.5, letterSpacing: .75, marginBottom: 6, fontWeight: 750 }}>
        EXCHANGE FILTERS
      </div>
      <div style={{ color: '#777', fontSize: 11.5, lineHeight: 1.5, marginBottom: 12 }}>
        Controls instruments shown in search, synced watchlists, ticker tiles and Sterling signals.
      </div>

      <div style={{ display: 'inline-flex', maxWidth: '100%', gap: 2, padding: 3, marginBottom: 14, border: '1px solid #e0e0e0', borderRadius: 8, background: '#f6f6f7', flexWrap: 'wrap' }}>
        <button
          type="button"
          onClick={() => apply(DEFAULT_KITE_EXCHANGES)}
          aria-pressed={isDefault}
          style={presetStyle(isDefault)}
        >
          NSE + NFO
        </button>
        <button
          type="button"
          onClick={() => apply(KITE_EXCHANGES)}
          aria-pressed={isAll}
          style={presetStyle(isAll)}
        >
          All exchanges
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 8 }}>
        {KITE_EXCHANGES.map((exchange) => {
          const active = selected.includes(exchange);
          return (
            <label
              key={exchange}
              style={{
                minHeight: 42, display: 'flex', alignItems: 'center', gap: 9, padding: '7px 10px',
                border: `1px solid ${active ? '#e2b6a4' : '#e0e0e0'}`,
                background: active ? '#fff5f0' : '#fff',
                borderRadius: 7, cursor: 'pointer', color: '#444',
                fontSize: 12, fontWeight: active ? 700 : 500,
              }}
            >
              <input
                type="checkbox"
                checked={active}
                onChange={() => toggle(exchange)}
                style={{ accentColor: ORANGE, width: 14, height: 14 }}
              />
              {exchange}
            </label>
          );
        })}
      </div>

      <div style={{ color: '#9b9b9b', fontSize: 10.5, lineHeight: 1.5, marginTop: 10 }}>
        Default is NSE + NFO. BSE/BFO, currency exchanges and MCX commodities are opt-in.
      </div>
    </div>
  );
}

export default KiteExchangeSettingsCard;
