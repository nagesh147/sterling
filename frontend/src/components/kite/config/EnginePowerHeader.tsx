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
  name, tagline, on, busy, onToggle, runningNote, offNote, children,
}: {
  name: string;
  tagline: string;
  on: boolean;
  busy?: boolean;
  onToggle: () => void;
  runningNote: string;
  offNote: string;
  children?: React.ReactNode;
}) {
  return (
    <section style={{
      ...settingsCardStyle,
      borderLeft: `3px solid ${on ? '#f06428' : '#c9c9c9'}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', padding: '16px 18px' }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
            <span style={{ color: TEXT, fontSize: 15, fontWeight: 800 }}>{name}</span>
            <span style={{
              padding: '2px 8px', borderRadius: 20, fontSize: 9, fontWeight: 800, letterSpacing: .4,
              color: on ? '#2e7d32' : MUTED,
              background: on ? '#e8f5e9' : SOFT,
              border: `1px solid ${on ? '#cfe2d0' : BORDER}`,
            }}>
              {on ? 'RUNNING' : 'OFF'}
            </span>
          </div>
          <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.5, marginTop: 4 }}>{tagline}</div>
          <div style={{ color: MUTED, fontSize: 11, lineHeight: 1.5, marginTop: 6 }}>
            {on ? runningNote : offNote}
          </div>
        </div>
        <Switch checked={on} label={`${name} engine`} disabled={busy} onChange={onToggle} />
      </div>
      {children}
    </section>
  );
}

export default EnginePowerHeader;
