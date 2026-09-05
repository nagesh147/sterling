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

  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    const active = wrap?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!wrap || !active) return;
    setBox({ left: active.offsetLeft, width: active.offsetWidth });
  }, [value, items]);

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
