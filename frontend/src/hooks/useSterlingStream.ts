import { useState, useEffect, useRef } from 'react';

// Get the WS URL from the env or infer it from the current location
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS_URL = API_URL.replace(/^http/, 'ws') + "/api/v1/stream/ws";

export type StreamStatus = 'connected' | 'reconnecting' | 'disconnected';

export interface StreamMetrics {
  ofi: number;
  unrealized_pnl: number;
  drift_bps: number;
}

export function useSterlingStream(symbol: string) {
  const [status, setStatus] = useState<StreamStatus>('disconnected');
  const [metrics, setMetrics] = useState<StreamMetrics>({
    ofi: 0,
    unrealized_pnl: 0,
    drift_bps: 0,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    if (!symbol) return;

    let isSubscribed = true;

    const connect = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        return; // Already connected
      }

      setStatus('reconnecting');
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isSubscribed) return;
        setStatus('connected');
        
        // Subscribe to the symbol channel
        ws.send(JSON.stringify({
          action: 'subscribe',
          channel: symbol
        }));
      };

      ws.onmessage = (event) => {
        if (!isSubscribed) return;
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'metrics_update' && payload.symbol === symbol && payload.data) {
            setMetrics(prev => ({
              ...prev,
              ...payload.data
            }));
          }
        } catch (err) {
          console.error("Error parsing stream message:", err);
        }
      };

      ws.onclose = () => {
        if (!isSubscribed) return;
        setStatus('disconnected');
        wsRef.current = null;
        
        // Auto-reconnect after 3 seconds
        if (reconnectTimeoutRef.current) {
          window.clearTimeout(reconnectTimeoutRef.current);
        }
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 3000);
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        // onclose will handle the reconnection
        ws.close();
      };
    };

    connect();

    return () => {
      isSubscribed = false;
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [symbol]);

  return { status, metrics };
}
