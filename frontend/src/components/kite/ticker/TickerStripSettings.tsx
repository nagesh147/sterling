/**
 * The pinned-instrument strip's appearance, in Experience settings.
 *
 * Three decisions, in the order a user makes them: whether the strip is there
 * at all, how each instrument is drawn, and how big.
 *
 * Every preset is shown as a live tile rather than a name in a list. A label
 * like "Chart-led" or "Heat" does not tell anyone what they are about to get,
 * and a preview built from the real renderer cannot drift from what ships.
 */
import React from 'react';
import { useTickerPins } from '../../../store/useTickerPins';
import { TILE_STYLES, type TickerTileStyle } from '../../../utils/tickerTileStyles';
import { TickerTile, type TileData } from './TickerTile';
import { k, tint } from '../../../styles/kiteUI';

/**
 * A plausible index, so every preview shows the same move and the presets can
 * be compared on presentation alone. Rising, because a green preview reads as
 * a sample rather than as an alert.
 */
const SAMPLE: TileData = {
  symbol: 'NSE:NIFTY 50',
  primary: 'NIFTY 50',
  secondary: '',
  market: 'INDEX',
  last: 24231.85,
  change: 153.55,
  changePct: 0.64,
  open: 24110.2,
  high: 24268.4,
  low: 24081.75,
  series: [24090, 24105, 24098, 24140, 24132, 24175, 24160, 24205, 24198, 24232],
};

const SCALE_MIN = 0.78;
const SCALE_MAX = 1.34;
const SCALE_STEP = 0.02;

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, padding: '10px 0', borderBottom: `1px solid ${k.border}` }}>
      <div style={{ width: 168, flexShrink: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: k.text }}>{label}</div>
        {hint && <div style={{ fontSize: 10.5, color: k.dim, lineHeight: 1.45, marginTop: 2 }}>{hint}</div>}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
    </div>
  );
}

export function TickerStripSettings() {
  const stripEnabled = useTickerPins((s) => s.stripEnabled ?? true);
  const setStripEnabled = useTickerPins((s) => s.setStripEnabled);
  const tileStyle = useTickerPins((s) => s.tileStyle ?? 'card');
  const setTileStyle = useTickerPins((s) => s.setTileStyle);
  const tileScale = useTickerPins((s) => s.tileScale ?? 1);
  const setTileScale = useTickerPins((s) => s.setTileScale);
  const resetAppearance = useTickerPins((s) => s.resetAppearance);
  const pinCount = useTickerPins((s) => s.pins.length);

  const isDefault = stripEnabled && tileStyle === 'card' && Math.abs(tileScale - 1) < 0.001;

  return (
    <section style={{ marginBottom: 16, padding: 18, background: k.bg, border: `1px solid ${k.border}`, borderRadius: 9 }}>
      <header style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 4 }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: k.text }}>Instrument strip</h3>
        <span style={{ fontSize: 10.5, color: k.dim }}>
          {pinCount} pinned{pinCount === 0 ? ' — pin one from a watchlist or a signal row' : ''}
        </span>
        {!isDefault && (
          <button
            type="button"
            onClick={resetAppearance}
            style={{
              marginLeft: 'auto', border: `1px solid ${tint(k.orange, 40)}`, background: tint(k.orange, 10),
              color: k.orange, borderRadius: 3, padding: '2px 7px', fontSize: 9.5, fontWeight: 700,
              fontFamily: 'inherit', cursor: 'pointer',
            }}
          >
            Reset appearance ↺
          </button>
        )}
      </header>

      <Row label="Show the strip" hint="Turning it off frees the space and keeps your pins.">
        <button
          type="button"
          role="switch"
          aria-checked={stripEnabled}
          aria-label="Show the instrument strip"
          onClick={() => setStripEnabled(!stripEnabled)}
          style={{
            width: 34, height: 18, borderRadius: 9, border: 'none', padding: 0, position: 'relative',
            background: stripEnabled ? k.orange : 'var(--k-faint-5)', cursor: 'pointer',
          }}
        >
          <span style={{
            position: 'absolute', top: 2, left: stripEnabled ? 18 : 2, width: 14, height: 14,
            borderRadius: 7, background: k.bg, transition: 'left .15s ease',
          }} />
        </button>
      </Row>

      <Row
        label="Tile style"
        hint="Each one shows the same facts. What changes is which of them get the space."
      >
        <div
          role="radiogroup"
          aria-label="Tile style"
          style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(196px, 1fr))', gap: 8 }}
        >
          {TILE_STYLES.map((meta) => {
            const on = meta.id === tileStyle;
            return (
              <button
                key={meta.id}
                type="button"
                role="radio"
                aria-checked={on}
                title={meta.hint}
                onClick={() => setTileStyle(meta.id as TickerTileStyle)}
                disabled={!stripEnabled}
                style={{
                  textAlign: 'left', padding: 8, borderRadius: 6, cursor: stripEnabled ? 'pointer' : 'default',
                  border: `1px solid ${on ? k.orange : k.border}`,
                  background: on ? tint(k.orange, 7) : k.surface,
                  fontFamily: 'inherit', opacity: stripEnabled ? 1 : 0.5,
                  display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0,
                }}
              >
                <span style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: on ? k.orange : k.text }}>{meta.label}</span>
                  {on && <span style={{ fontSize: 8.5, fontWeight: 700, color: k.orange, letterSpacing: '.05em' }}>IN USE</span>}
                </span>
                {/* The real renderer, so a preview cannot drift from what ships. */}
                <span style={{ display: 'block', overflow: 'hidden', pointerEvents: 'none' }}>
                  <TickerTile style={meta.id as TickerTileStyle} data={SAMPLE} scale={0.82} />
                </span>
                <span style={{ fontSize: 9.5, color: k.dim, lineHeight: 1.4 }}>{meta.hint}</span>
              </button>
            );
          })}
        </div>
      </Row>

      <Row label="Size" hint="Scales every tile together, so the strip keeps one rhythm.">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <input
            type="range"
            min={SCALE_MIN}
            max={SCALE_MAX}
            step={SCALE_STEP}
            value={tileScale}
            disabled={!stripEnabled}
            aria-label="Tile size"
            onChange={(e) => setTileScale(Number(e.target.value))}
            style={{ flex: '0 1 220px', accentColor: k.orange }}
          />
          <span style={{ fontSize: 11, color: k.text, fontVariantNumeric: 'tabular-nums', minWidth: 42 }}>
            {Math.round(tileScale * 100)}%
          </span>
        </div>
        <div style={{ marginTop: 10, padding: 10, border: `1px dashed ${k.border}`, borderRadius: 6, background: k.surface, overflow: 'hidden' }}>
          <div style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '.06em', color: k.dim, marginBottom: 6 }}>PREVIEW AT THIS SIZE</div>
          <TickerTile style={tileStyle as TickerTileStyle} data={SAMPLE} scale={tileScale} />
        </div>
      </Row>
    </section>
  );
}
