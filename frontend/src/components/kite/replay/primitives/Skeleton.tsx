import React from 'react';

/** Placeholder rows while the runner hydrates candles. */
export function SkeletonRows({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div aria-hidden="true" data-testid="replay-skeleton">
      {Array.from({ length: rows }, (_, r) => (
        <div className="rd-skel-row" key={r}>
          {Array.from({ length: cols }, (_, c) => (
            <span
              className="rd-skel"
              key={c}
              style={{ flex: c === cols - 1 ? '0 0 60px' : c === 2 ? 2 : 1 }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
