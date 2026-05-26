import React from 'react';
import { useDrawdownBreaker, useResetDrawdownBreaker } from '../hooks/useDrawdownBreaker';
import { useQueryClient } from '@tanstack/react-query';
import { c as t, tint } from '../styles/terminalUI';

export function DrawdownBreakerBadge() {
  const { data } = useDrawdownBreaker();
  const { mutate: reset, isPending: resetting } = useResetDrawdownBreaker();
  const qc = useQueryClient();

  if (!data || data.state === 'clear') return null;

  const configs: Record<string, { bg: string; text: string; border: string; message: string }> = {
    warning: {
      bg: tint(t.amber, 12), text: t.amber, border: tint(t.amber, 33),
      message: `Drawdown warning — position size halved (DD: ${(Math.abs(data.current_drawdown) * 100).toFixed(1)}%)`,
    },
    halt: {
      bg: tint(t.red, 12), text: t.red, border: tint(t.red, 33),
      message: `Trading halted — drawdown exceeded 10% (DD: ${(Math.abs(data.current_drawdown) * 100).toFixed(1)}%)`,
    },
    reset: {
      bg: tint(t.red, 12), text: t.red, border: tint(t.red, 53),
      message: `Manual reset required — drawdown ${(Math.abs(data.current_drawdown) * 100).toFixed(1)}%`,
    },
  };

  const cfg = configs[data.state];
  if (!cfg) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999,
      background: cfg.bg, border: `1px solid ${cfg.border}`,
      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16,
      padding: '8px 20px',
    }}>
      <span style={{ color: cfg.text, fontSize: 12, fontWeight: 700 }}>{cfg.message}</span>
      {data.state === 'reset' && (
        <button
          disabled={resetting}
          onClick={() => reset(undefined, { onSuccess: () => qc.invalidateQueries({ queryKey: ['dd-circuit-breaker'] }) })}
          style={{
            background: tint(t.blue, 14), color: t.blue, border: `1px solid ${t.blue}`,
            borderRadius: 3, padding: '3px 12px', cursor: 'pointer',
            fontFamily: 'inherit', fontSize: 11,
          }}
        >
          {resetting ? 'Resetting…' : 'Reset'}
        </button>
      )}
    </div>
  );
}
