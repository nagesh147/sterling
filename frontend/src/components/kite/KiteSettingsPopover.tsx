import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { k } from '../../styles/kiteUI';
import { useKiteSettings } from '../../store/useKiteSettings';
import { useTickerPins } from '../../store/useTickerPins';
import {
  DEFAULT_KITE_EXCHANGES,
  KITE_EXCHANGES,
  exchangeFromSymbol,
  isKiteExchangeEnabled,
  readKiteExchanges,
  writeKiteExchanges,
  type KiteExchange,
} from '../../utils/kiteExchanges';

const TOGGLES: Array<{ key: 'showHoldings' | 'showNotes' | 'showGroupColors' | 'showExchange' | 'showLeg'; label: string }> = [
  { key: 'showHoldings', label: 'Show holdings in watchlist' },
  { key: 'showNotes', label: 'Show notes' },
  { key: 'showGroupColors', label: 'Show group colours' },
  { key: 'showExchange', label: 'Show exchange badge' },
  { key: 'showLeg', label: 'Show leg labels' },
];

export function KiteSettingsPopover({ onClose }: { onClose: () => void }) {
  const settings = useKiteSettings();
  const queryClient = useQueryClient();
  const [exchanges, setExchanges] = React.useState<KiteExchange[]>(() => readKiteExchanges());

  const applyExchanges = (next: readonly string[]) => {
    const saved = writeKiteExchanges(next);
    setExchanges(saved);
    useTickerPins.setState((state) => ({
      pins: state.pins.filter((symbol) => isKiteExchangeEnabled(exchangeFromSymbol(symbol), saved)),
    }));
    void queryClient.invalidateQueries({ queryKey: ['kite-instruments'] });
    void queryClient.invalidateQueries({ queryKey: ['kite-engine-signals'] });
    void queryClient.invalidateQueries({ queryKey: ['kite-engine-scan-report'] });
    void queryClient.invalidateQueries({ queryKey: ['kite-engine-open-positions'] });
  };

  const toggleExchange = (exchange: KiteExchange) => {
    const next = exchanges.includes(exchange)
      ? exchanges.filter((item) => item !== exchange)
      : [...exchanges, exchange];
    applyExchanges(next.length ? next : DEFAULT_KITE_EXCHANGES);
  };

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 60, right: 40, width: 320, maxWidth: '92vw', maxHeight: 'calc(100vh - 80px)', overflowY: 'auto', background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily, padding: '16px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 500, color: '#444' }}>Display settings</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 16, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>

        <div style={{ paddingBottom: 12, marginBottom: 8, borderBottom: `1px solid ${k.border}` }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 7 }}>
            <div>
              <div style={{ fontSize: 12.5, color: '#444', fontWeight: 500 }}>Exchanges</div>
              <div style={{ fontSize: 10.5, color: k.dim, marginTop: 2 }}>Controls instrument searches, ticker tiles, and Sterling signals.</div>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button type="button" onClick={() => applyExchanges(DEFAULT_KITE_EXCHANGES)} style={{ border: `1px solid ${k.border}`, background: k.bg, color: k.blue, borderRadius: 3, padding: '3px 6px', fontSize: 10, cursor: 'pointer' }}>NSE market</button>
              <button type="button" onClick={() => applyExchanges(KITE_EXCHANGES)} style={{ border: `1px solid ${k.border}`, background: k.bg, color: k.blue, borderRadius: 3, padding: '3px 6px', fontSize: 10, cursor: 'pointer' }}>All</button>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '4px 10px' }}>
            {KITE_EXCHANGES.map((exchange) => (
              <label key={exchange} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: '#444', cursor: 'pointer', padding: '4px 0' }}>
                <input type="checkbox" checked={exchanges.includes(exchange)} onChange={() => toggleExchange(exchange)} style={{ accentColor: k.blue, width: 14, height: 14 }} />
                {exchange}
              </label>
            ))}
          </div>
          <div style={{ fontSize: 10, color: k.dim, marginTop: 5 }}>Default: NSE + NFO. BSE/BFO, currencies, and commodities are opt-in.</div>
        </div>

        {TOGGLES.map(({ key, label }) => (
          <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: '#444', cursor: 'pointer', padding: '6px 0' }}>
            <input type="checkbox" checked={settings[key]} onChange={() => settings.toggleShow(key)} style={{ accentColor: k.blue, width: 14, height: 14 }} />
            {label}
          </label>
        ))}
      </div>
    </>
  );
}
