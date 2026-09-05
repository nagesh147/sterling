import React, { useMemo, useRef, useState } from 'react';

export type SparkPoint = { x: number; y: number; label?: string };

/**
 * Cumulative equity curve.
 *
 * The version this replaces was a bare `<polyline>` in a fixed 430×44 viewBox
 * with `preserveAspectRatio="none"`, so the line was horizontally stretched by
 * whatever width it landed in and the slope meant nothing. This one keeps its
 * aspect, draws the zero baseline (without which profit and loss are visually
 * identical), and shades the worst peak-to-trough run, which is the number a
 * trader actually wants from an equity curve.
 */
export function Sparkline({
  values,
  height = 120,
  caption,
}: {
  values: readonly number[];
  height?: number;
  caption?: string;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null);

  const W = 1000;                // virtual units; the SVG scales to its box
  const PAD = 6;

  const model = useMemo(() => {
    if (values.length < 2) return null;
    const min = Math.min(...values, 0);
    const max = Math.max(...values, 0);
    const range = max - min || 1;
    const H = height;

    const xFor = (i: number) => (i / (values.length - 1)) * W;
    const yFor = (v: number) => H - PAD - ((v - min) / range) * (H - PAD * 2);

    const pts = values.map((v, i) => `${xFor(i)},${yFor(v)}`);
    const line = pts.join(' ');
    const area = `${xFor(0)},${yFor(min)} ${line} ${xFor(values.length - 1)},${yFor(min)}`;

    // Worst peak-to-trough run over the cumulative series.
    let peak = values[0];
    let peakAt = 0;
    let ddFrom = 0;
    let ddTo = 0;
    let worst = 0;
    values.forEach((v, i) => {
      if (v > peak) {
        peak = v;
        peakAt = i;
      }
      const dd = peak - v;
      if (dd > worst) {
        worst = dd;
        ddFrom = peakAt;
        ddTo = i;
      }
    });

    return {
      line,
      area,
      xFor,
      yFor,
      zeroY: yFor(0),
      drawdown: worst > 0 ? { from: xFor(ddFrom), to: xFor(ddTo), depth: worst } : null,
      last: values[values.length - 1],
      H,
    };
  }, [values, height]);

  if (!model) return null;

  const tone = model.last >= 0 ? 'var(--k-green)' : 'var(--k-red-brick)';

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - box.left) / box.width;
    const i = Math.round(Math.max(0, Math.min(1, ratio)) * (values.length - 1));
    setHover({ i, x: e.clientX - box.left, y: 0 });
  };

  return (
    <div className="rd-curve" ref={hostRef}>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${W} ${model.H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Cumulative realised profit and loss across ${values.length - 1} trades`}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {model.drawdown && (
          <rect
            x={model.drawdown.from}
            y={0}
            width={Math.max(1, model.drawdown.to - model.drawdown.from)}
            height={model.H}
            fill="var(--k-red-brick)"
            opacity="0.1"
          />
        )}
        <polyline
          points={model.area}
          fill={tone}
          opacity="0.12"
          stroke="none"
        />
        <line
          x1={0}
          x2={W}
          y1={model.zeroY}
          y2={model.zeroY}
          stroke="var(--k-border)"
          strokeWidth="1"
          strokeDasharray="4 4"
          vectorEffect="non-scaling-stroke"
        />
        <polyline
          points={model.line}
          fill="none"
          stroke={tone}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        {hover && (
          <line
            x1={model.xFor(hover.i)}
            x2={model.xFor(hover.i)}
            y1={0}
            y2={model.H}
            stroke="var(--k-dim)"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>
      {hover && (
        <span
          className="rd-curve-tip"
          style={{ left: hover.x, top: 4 }}
        >
          {hover.i === 0 ? 'start' : `trade ${hover.i}`} · {values[hover.i] >= 0 ? '+' : '−'}₹
          {Math.abs(values[hover.i]).toFixed(2)}
        </span>
      )}
      {caption && <div className="rd-curve-caption">{caption}</div>}
    </div>
  );
}
