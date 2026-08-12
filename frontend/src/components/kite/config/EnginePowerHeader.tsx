import React from 'react';
import { BORDER, MUTED, SOFT, Switch, TEXT, settingsCardStyle } from '../kiteSettingsPrimitives';

/**
 * The on/off header every signal engine gets, in the same shape.
 *
 * SuperTrend used to be armed by a switch on one page while Navigator was armed
 * by a switch buried inside its own settings, and Trading Mode offered SuperTrend
 * a toggle but Navigator only a "Configure \u2192" button. Two engines that are peers
 * should not be operated through two different idioms \u2014 the reader ends up
 * believing one is the real engine and the other an add-on.
 */
export function EnginePowerHeader({
  name, tagline, on, liveOn, busy, onToggle, runningNote, offNote, children,
}: {
  name: string;
  /** Draft state — what the switch shows, so the toggle stays responsive. */
  on: boolean;
  /**
   * What the SERVER currently has, which is what is actually scanning and placing
   * orders. The badge, the note and the border read from this.
   *
   * The switch is a draft edit like everything else on these pages, but the
   * RUNNING/OFF badge used to be rendered from that same draft — so flipping the
   * switch repainted the card to "OFF / Not scanning" while nothing had been sent
   * anywhere. Leave the page without applying (switching settings sections unmounts
   * the panel and drops the draft) and the engine is still scanning and still
   * eligible for automatic execution, having told you it was off. That is a kill
   * switch reporting a state it has not reached.
   *
   * Omit it and the old behaviour stands, for callers with no server value to hand.
   */
  liveOn?: boolean;
  tagline: string;
  busy?: boolean;
  onToggle: () => void;
  runningNote: string;
  offNote: string;
  children?: React.ReactNode;
}) {
  const live = liveOn ?? on;
  const pending = live !== on;

  return (
    <section style={{
      ...settingsCardStyle,
      borderLeft: `3px solid ${live ? '#f06428' : '#c9c9c9'}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', padding: '16px 18px' }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
            <span style={{ color: TEXT, fontSize: 15, fontWeight: 800 }}>{name}</span>
            <span style={{
              padding: '2px 8px', borderRadius: 20, fontSize: 9, fontWeight: 800, letterSpacing: .4,
              color: live ? '#2e7d32' : MUTED,
              background: live ? '#e8f5e9' : SOFT,
              border: `1px solid ${live ? '#cfe2d0' : BORDER}`,
            }}>
              {live ? 'RUNNING' : 'OFF'}
            </span>
            {pending && (
              <span style={{
                padding: '2px 8px', borderRadius: 20, fontSize: 9, fontWeight: 800, letterSpacing: .4,
                color: '#b06a13', background: '#fdf3e3', border: '1px solid #efd9b4',
              }}>
                {on ? 'WILL START ON APPLY' : 'WILL STOP ON APPLY'}
              </span>
            )}
          </div>
          <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.5, marginTop: 4 }}>{tagline}</div>
          <div style={{ color: MUTED, fontSize: 11, lineHeight: 1.5, marginTop: 6 }}>
            {live ? runningNote : offNote}
          </div>
          {pending && (
            <div style={{ color: '#b06a13', fontSize: 11, lineHeight: 1.5, marginTop: 6, fontWeight: 600 }}>
              {on
                ? `Not applied yet — ${name} is still off until you apply this.`
                : `Not applied yet — ${name} is still running until you apply this.`}
            </div>
          )}
        </div>
        <Switch checked={on} label={`${name} engine`} disabled={busy} onChange={onToggle} />
      </div>
      {children}
    </section>
  );
}

export default EnginePowerHeader;
