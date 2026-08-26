/**
 * Display scale, in Experience settings.
 *
 * The setting exists because the app used to look like a different product on
 * every monitor: a browser hands the page a CSS-pixel viewport sized by the
 * display's scale factor, so the identical layout got 2540px of room on one
 * screen and 1234px on another — signal columns clipped on the second and
 * everything read half-size on the first.
 *
 * The app now lays out against a fixed design width and scales to fit, so the
 * three controls here are: whether to do that at all, how much to fit on
 * screen, and a manual nudge on top.
 *
 * The readout is the important part of this panel. "Density: standard" means
 * nothing on its own; showing that this monitor is being fitted to 2480×1215
 * at 0.50x, and whether that actually matched, makes the setting legible and
 * makes it obvious when two machines disagree — the exact problem the feature
 * exists to solve.
 */
import React from 'react';
import { Section, Field, ChoiceRow, Switch } from './kiteSettingsPrimitives';
import { k } from '../../styles/kiteUI';
import {
  DESIGN, DENSITY_ORDER, MIN_USER_SCALE, MAX_USER_SCALE, resolveScale, type Density,
} from '../../utils/viewportScale';
import {
  useDensity, useSetDensity, useAutoFitDensity, useSetAutoFitDensity,
  useZoomLevel, useStore,
} from '../../store/useStore';

const DENSITY_LABEL: Record<Density, { label: string; hint: string }> = {
  comfortable: { label: 'Comfortable', hint: 'Larger type, fewer columns' },
  standard: { label: 'Standard', hint: 'The full signal table' },
  compact: { label: 'Compact', hint: 'Most on screen at once' },
};

/** Re-renders on resize so the readout keeps telling the truth. */
function useViewportReadout() {
  const read = () => ({
    w: typeof window === 'undefined' ? 0 : window.innerWidth,
    h: typeof window === 'undefined' ? 0 : window.innerHeight,
    dpr: typeof window === 'undefined' ? 1 : window.devicePixelRatio,
  });
  const [size, setSize] = React.useState(read);
  React.useEffect(() => {
    const on = () => setSize(read());
    window.addEventListener('resize', on);
    return () => window.removeEventListener('resize', on);
  }, []);
  return size;
}

export function DisplayScaleSettings() {
  const density = useDensity();
  const setDensity = useSetDensity();
  const autoFit = useAutoFitDensity();
  const setAutoFit = useSetAutoFitDensity();
  const userScale = useZoomLevel();
  const setZoomLevel = useStore((s) => s.setZoomLevel);

  const { w, h, dpr } = useViewportReadout();
  const { scale, mode, layoutWidth, layoutHeight } = resolveScale({
    viewportWidth: w, viewportHeight: h, devicePixelRatio: dpr, density, userScale, autoFit,
  });
  const box = DESIGN[density];
  const layoutW = Math.round(layoutWidth);
  const layoutH = Math.round(layoutHeight);

  const summary = mode === 'off'
    ? `Off · ${userScale.toFixed(2)}×`
    : `${DENSITY_LABEL[density].label} · ${scale.toFixed(2)}× · ${mode}`;

  return (
    <Section
      title="Display scale"
      description="Keeps the app the same size and shape on every monitor, whatever scale factor the display reports."
      summary={summary}
      persistKey="display-scale"
    >
      <Field
        label="What stays the same across monitors"
        hint="You can hold one of these constant, not both. Off (the default) renders 1:1 like every other site, so text is the same physical size everywhere and the board drops columns when a screen is short of room. On holds the layout instead, so every screen shows identical content and text size follows the display."
        wide
      >
        <Switch
          checked={autoFit}
          label={autoFit ? 'Layout — same content, text size varies' : 'Text size — same type, content varies'}
          onChange={() => setAutoFit(!autoFit)}
        />
      </Field>

      <Field label="Density" hint="How much of the app to fit on screen at once." wide>
        <ChoiceRow<Density>
          value={density}
          options={DENSITY_ORDER.map((d) => ({
            value: d,
            label: DENSITY_LABEL[d].label,
            hint: DENSITY_LABEL[d].hint,
          }))}
          onChange={setDensity}
        />
      </Field>

      <Field
        label={`Manual zoom — ${userScale.toFixed(2)}×`}
        hint="Applied on top of the fit, for when the fitted size is not to your taste."
        wide
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <input
            type="range"
            min={MIN_USER_SCALE}
            max={MAX_USER_SCALE}
            step={0.05}
            value={userScale}
            aria-label="Manual zoom"
            onChange={(e) => setZoomLevel(Number(e.target.value))}
            style={{ flex: 1, accentColor: k.orange }}
          />
          <button
            type="button"
            onClick={() => setZoomLevel(1)}
            disabled={userScale === 1}
            style={{
              background: 'transparent',
              border: `1px solid ${k.border}`,
              borderRadius: 6,
              color: userScale === 1 ? k.dim : k.text,
              cursor: userScale === 1 ? 'default' : 'pointer',
              fontSize: 11,
              padding: '4px 9px',
            }}
          >
            Reset
          </button>
        </div>
      </Field>

      <div
        style={{
          marginTop: 4,
          padding: '10px 12px',
          background: 'var(--k-bg-soft, var(--k-bg))',
          border: `1px solid ${k.border}`,
          borderRadius: 8,
          color: k.dim,
          fontSize: 11,
          lineHeight: 1.6,
        }}
      >
        <div style={{ color: k.text, fontSize: 11, fontWeight: 600, marginBottom: 4 }}>
          This monitor
        </div>
        <div>
          Browser gives {w}×{h} CSS px · rendering at{' '}
          <strong style={{ color: k.text }}>{scale.toFixed(3)}×</strong>
        </div>
        <div>
          App lays out at{' '}
          <strong style={{ color: k.text }}>{layoutW}×{layoutH}</strong>
          {autoFit && <> · target {box.width}×{box.height}</>}
        </div>
        {mode === 'matched' && (
          <div style={{ marginTop: 4 }}>
            Matched — this screen lays out identically to every other matched screen.
          </div>
        )}
        {mode === 'responsive' && (
          <div style={{ marginTop: 4 }}>
            This display cannot show {box.width}×{box.height} at a readable size, so the app
            is rendering at 1:1 and adapting the layout instead. Choose a smaller density to
            bring it back into match.
          </div>
        )}
        {mode === 'off' && (
          <div style={{ marginTop: 4 }}>
            Rendering 1:1, so text is the same physical size as on any other
            screen and the board fits its columns to the room it has.
          </div>
        )}
      </div>
    </Section>
  );
}
