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

  return (
    <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: 4, padding: 16, marginBottom: 14 }}>
      <div style={{ color: '#9b9b9b', fontSize: 11, letterSpacing: 1, marginBottom: 6, fontWeight: 700 }}>
        EXCHANGE FILTERS
      </div>
      <div style={{ color: '#777', fontSize: 11.5, lineHeight: 1.5, marginBottom: 12 }}>
        Controls instruments shown in search, synced watchlists, ticker tiles and Sterling signals.
      </div>

      <div style={{ display: 'flex', gap: 7, marginBottom: 12, flexWrap: 'wrap' }}>
        <button
          type="button"
          onClick={() => apply(DEFAULT_KITE_EXCHANGES)}
          style={{ border: '1px solid #e0e0e0', background: '#fff', color: ORANGE, borderRadius: 4, padding: '5px 10px', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' }}
        >
          NSE market
        </button>
        <button
          type="button"
          onClick={() => apply(KITE_EXCHANGES)}
          style={{ border: '1px solid #e0e0e0', background: '#fff', color: '#387ed1', borderRadius: 4, padding: '5px 10px', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' }}
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
                display: 'flex', alignItems: 'center', gap: 8, padding: '9px 10px',
                border: `1px solid ${active ? ORANGE : '#e0e0e0'}`,
                background: active ? 'rgba(240,100,40,.055)' : '#fff',
                borderRadius: 5, cursor: 'pointer', color: active ? '#d35400' : '#444',
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
