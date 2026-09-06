import React, { useLayoutEffect, useRef, useState } from 'react';

export type SegmentedItem = {
  id: string;
  label: string;
  icon?: React.ReactNode;
  count?: number;
};

/**
 * A tab strip with a sliding indicator.
 *
 * The indicator is driven by MEASURED offsets rather than `nth-child` maths,
 * because the labels carry live counts and change width as the replay runs.
 */
export function Segmented<T extends string>({
  items,
  value,
  onChange,
  label,
  idPrefix,
}: {
  items: readonly SegmentedItem[];
  value: T;
  onChange: (id: T) => void;
  label: string;
  idPrefix: string;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<{ left: number; width: number } | null>(null);

  /* Callers build `items` inline, so its identity changes on EVERY render of the
     parent. Depending on that identity re-ran this effect every render, and
     `setBox` always stored a fresh object — never `Object.is`-equal to the last
     one, so React re-rendered, which re-ran the effect, forever. That is a hard
     "Maximum update depth exceeded" crash that takes the whole app down with it.

     Depend on the CONTENT that can move the indicator, and write state only when
     the measurement actually changed. */
  const shape = items.map((i) => `${i.id}:${i.label}:${i.count ?? ''}`).join('|');

  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    const active = wrap?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!wrap || !active) return;
    const left = active.offsetLeft;
    const width = active.offsetWidth;
    setBox((prev) => (prev && prev.left === left && prev.width === width
      ? prev
      : { left, width }));
  }, [value, shape]);

  return (
    <div className="rd-seg" role="tablist" aria-label={label} ref={wrapRef}>
      {box && (
        <span
          className="rd-seg-indicator"
          aria-hidden="true"
          style={{ transform: `translateX(${box.left}px)`, width: box.width }}
        />
      )}
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          id={`${idPrefix}-tab-${item.id}`}
          aria-controls={`${idPrefix}-panel-${item.id}`}
          aria-selected={value === item.id}
          tabIndex={value === item.id ? 0 : -1}
          className="rd-seg-btn"
          onClick={() => onChange(item.id as T)}
          onKeyDown={(e) => {
            if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
            e.preventDefault();
            const i = items.findIndex((x) => x.id === value);
            const next = e.key === 'ArrowRight' ? i + 1 : i - 1;
            onChange(items[(next + items.length) % items.length].id as T);
          }}
        >
          {item.icon}
          {item.label}
          {item.count != null && <span className="rd-seg-count">{item.count}</span>}
        </button>
      ))}
    </div>
  );
}
