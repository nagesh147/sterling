import React, { useState, useEffect, useRef } from 'react';
import { card, cardHead, cardBody, c, alpha } from '../styles/terminalUI';

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={card}>
      <div style={cardHead}><span>{title}</span></div>
      <div style={cardBody}>{children}</div>
    </div>
  );
}

export function GrokLogsPane() {
  const [logs, setLogs] = useState<{msg: string, time: string, color: string}[]>([
    {msg: "Engine initialized. Loading edge configurations...", time: "10:45:02", color: c.dim},
    {msg: "[PASS] BTCUSD 15m bb_rsi_reversion (DSR: 0.88, WFA: 80%)", time: "10:45:03", color: c.green},
    {msg: "[PASS] SOLUSD 15m vwap_cross (DSR: 0.84, WFA: 60%)", time: "10:45:03", color: c.green},
    {msg: "Arbitrator active. Awaiting signals.", time: "10:45:06", color: c.amber}
  ]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      ws = new WebSocket(`ws://${window.location.hostname}:8000/api/v1/stream/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ action: "subscribe", channel: "arbitrator_logs" }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.type === "log" && data.message) {
            let color: string = c.bright;
            if (data.level === "ERROR" || data.level === "CRITICAL") color = c.red;
            else if (data.level === "WARNING") color = c.amber;
            else if (data.level === "DEBUG") color = c.dim;

            const timeMatch = data.message.match(/^(\d{2}:\d{2}:\d{2})/);
            const timeStr = timeMatch ? timeMatch[1] : new Date().toLocaleTimeString('en-US', {hour12: false});
            let cleanMsg = data.message;
            if (timeMatch) {
              cleanMsg = cleanMsg.substring(timeMatch[0].length).trim();
            }

            setLogs(prev => {
              const newLogs = [...prev, { msg: cleanMsg, time: timeStr, color }];
              if (newLogs.length > 50) return newLogs.slice(newLogs.length - 50);
              return newLogs;
            });
          }
        } catch (e) { }
      };

      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 16 }}>
      <div style={{ 
        fontFamily: 'JetBrains Mono, monospace', 
        fontSize: 9, 
        display: 'flex', 
        flexDirection: 'column', 
        gap: 6,
        lineHeight: 1.4,
        maxHeight: '400px',
        overflowY: 'auto'
      }}>
        {logs.map((log, i) => (
          <div key={i} style={{ color: log.color, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            <span style={{ color: c.dim }}>[{log.time}]</span> {log.msg}
          </div>
        ))}
      </div>
    </div>
  );
}

