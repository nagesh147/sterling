/**
 * useAllSignalsStream — thin wrapper over useAppStream singleton.
 *
 * Returns the same shape as before so it is a drop-in replacement.
 * Price updates from the 'prices' event are merged into signal data
 * so spot_price fields stay current between 'signals' refreshes.
 */
import { useEffect, useRef, useState } from 'react';
import { useAppStream } from './useAppStream';
import type { SignalItem, SignalsResponse } from './useSignals';

export type { StreamStatus } from './useAppStream';

export function useAllSignalsStream(): { data: SignalsResponse | null; status: import('./useAppStream').StreamStatus } {
  const { data: signalPayload, status } = useAppStream<{ signals: SignalItem[]; timestamp_ms: number }>('signals');
  const { data: priceMap }              = useAppStream<Record<string, number>>('prices');

  const [data, setData] = useState<SignalsResponse | null>(null);
  const dataRef = useRef<SignalsResponse | null>(null);

  // Full signals replacement
  useEffect(() => {
    if (!signalPayload) return;
    const next: SignalsResponse = {
      signals: signalPayload.signals,
      count:   signalPayload.signals.length,
      timestamp_ms: signalPayload.timestamp_ms,
    };
    dataRef.current = next;
    setData(next);
  }, [signalPayload]);

  // Merge spot prices into existing signals
  useEffect(() => {
    if (!priceMap || !dataRef.current) return;
    let changed = false;
    const updated = dataRef.current.signals.map(sig => {
      const p = priceMap[sig.underlying];
      if (p == null || p === sig.spot_price) return sig;
      changed = true;
      return { ...sig, spot_price: p };
    });
    if (!changed) return;
    const next: SignalsResponse = {
      ...dataRef.current,
      signals: updated,
      timestamp_ms: Date.now(),
    };
    dataRef.current = next;
    setData(next);
  }, [priceMap]);

  return { data, status };
}
