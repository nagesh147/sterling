/**
 * useLivePrices — thin wrapper over useAppStream singleton.
 *
 * All component instances share one SSE connection (managed by useAppStream).
 * A symbol is considered stale if no SSE price event arrived for it in 30s.
 */
import { useEffect, useRef, useState } from 'react';
import { useAppStream } from './useAppStream';

const STALE_MS = 30_000;

let _prices: Record<string, number> = {};
let _receivedAt: Record<string, number> = {};

function freshPrices(): Record<string, number> {
  const now = Date.now();
  const out: Record<string, number> = {};
  for (const [sym, price] of Object.entries(_prices)) {
    if (now - (_receivedAt[sym] ?? 0) < STALE_MS) out[sym] = price;
  }
  return out;
}

export function useLivePrices(): Record<string, number> {
  const { data: incoming } = useAppStream<Record<string, number>>('prices');
  const [prices, setPrices] = useState<Record<string, number>>(() => freshPrices());
  const setPricesRef = useRef(setPrices);
  setPricesRef.current = setPrices;

  useEffect(() => {
    if (!incoming) return;
    const now = Date.now();
    let changed = false;
    for (const [sym, price] of Object.entries(incoming)) {
      _receivedAt[sym] = now;
      if (_prices[sym] !== price) {
        _prices = { ..._prices, [sym]: price };
        changed = true;
      }
    }
    if (changed || Object.keys(incoming).length > 0) {
      setPricesRef.current(freshPrices());
    }
  }, [incoming]);

  return prices;
}
