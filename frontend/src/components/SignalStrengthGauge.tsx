import React from 'react';

interface SignalStrengthGaugeProps {
  strength: number;
  size?: 'sm' | 'md';
}

function segmentColor(strength: number): string {
  if (strength < 40) return 'var(--color-danger, #cc4444)';
  if (strength < 60) return 'var(--color-warning, #f0c040)';
  if (strength < 80) return 'var(--color-info, #4499cc)';
  return 'var(--color-success, #44cc88)';
}

export function SignalStrengthGauge({ strength, size = 'sm' }: SignalStrengthGaugeProps) {
  const segments = 10;
  const filled = Math.round((Math.min(100, Math.max(0, strength)) / 100) * segments);
  const color = segmentColor(strength);
  const segW = size === 'md' ? 10 : 7;
  const segH = size === 'md' ? 14 : 10;
  const gap = 2;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap }}>
      {Array.from({ length: segments }).map((_, i) => (
        <div
          key={i}
          title={`Signal: ${strength.toFixed(0)}%`}
          style={{
            width: segW, height: segH,
            borderRadius: 2,
            background: i < filled ? color : '#1e1e1e',
            border: `1px solid ${i < filled ? color : '#333'}`,
            transition: 'background 0.2s',
          }}
        />
      ))}
    </div>
  );
}
