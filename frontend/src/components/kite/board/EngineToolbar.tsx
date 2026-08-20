/**
 * The chrome above every signal board.
 *
 * Replaces two problems at once.
 *
 * The engine picker was three flat text tabs that said only a name — nothing
 * about whether an engine was even running, or whether it had anything for you.
 * Now each tab carries a live state dot and its armed count, so the choice of
 * where to look is informed before you look.
 *
 * The control strip was a single row mixing three unrelated kinds of control:
 * server-side engine config (SOURCE, EXIT), local view filters (VIEW, Best,
 * Ended), and actions (rescan, settings). Worse, SOURCE and EXIT are SuperTrend
 * rules that were sitting above Navigator rows they could not affect. Controls
 * now declare their `scope`, and a control whose engine is not on screen is not
 * rendered — a live setting next to rows it does not govern is a lie about what
 * changing it will do.
 *
 * The layout is a fixed grammar so muscle memory survives switching engines:
 *
 *   [ engine tabs ........................ ] [ rescan ] [ settings ]
 *   [ search ................. ] [ filters ] [ engine-specific controls ]
 */
import React from 'react';
import { k, tint } from '../../../styles/kiteUI';
import { ENGINE_LABEL, type EngineId } from './boardTypes';

export interface EngineTabState {
  id: EngineId;
  /** Server-side on/off. A stopped engine still gets a tab — it explains itself. */
  running: boolean;
  /** Rows worth acting on right now. Drives the count badge. */
  armed: number;
  /** Total scanned, for the "0 of 18" case that means "working, nothing yet". */
  scanned: number;
}

function StateDot({ running, armed }: { running: boolean; armed: number }) {
  const tone = !running ? k.dim : armed > 0 ? k.green : k.amber;
  return (
    <span
      aria-hidden
      title={!running ? 'Not scanning' : armed > 0 ? `${armed} armed` : 'Scanning, nothing armed'}
      style={{
        width: 6, height: 6, borderRadius: '50%', background: tone, flexShrink: 0,
        // Only a live, armed engine pulses. Motion is reserved for the one
        // state that wants attention, or it stops meaning anything.
        animation: running && armed > 0 ? 'sb-pulse 1.8s ease-in-out infinite' : undefined,
      }}
    />
  );
}

export function EngineTabs({ tabs, active, onSelect }: {
  tabs: readonly EngineTabState[];
  active: EngineId;
  onSelect: (id: EngineId) => void;
}) {
  return (
    <div role="tablist" aria-label="Signal engine" style={{ display: 'flex', flex: 1, minWidth: 0 }}>
      {tabs.map((tab) => {
        const on = tab.id === active;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={on}
            aria-label={`${ENGINE_LABEL[tab.id]}, ${tab.running ? `${tab.armed} armed of ${tab.scanned} scanned` : 'not scanning'}`}
            onClick={() => onSelect(tab.id)}
            className="sb-tab"
            style={{
              flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              padding: '7px 6px', border: 0,
              borderBottom: `2px solid ${on ? 'var(--k-brand)' : 'transparent'}`,
              background: 'transparent',
              color: on ? k.text : k.dim,
              fontSize: 9.5, fontWeight: on ? 700 : 500, letterSpacing: '.05em',
              fontFamily: 'inherit', cursor: 'pointer', whiteSpace: 'nowrap',
            }}
          >
            <StateDot running={tab.running} armed={tab.armed} />
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{ENGINE_LABEL[tab.id].toUpperCase()}</span>
            {tab.running && tab.armed > 0 && (
              <span style={{
                fontSize: 8.5, fontWeight: 700, color: k.green, background: tint(k.green, 14),
                border: `1px solid ${tint(k.green, 35)}`, borderRadius: 8, padding: '0 4px', minWidth: 14, textAlign: 'center',
              }}>
                {tab.armed}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function ToolbarButton({ title, onClick, active, disabled, children }: {
  title: string;
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      aria-pressed={active}
      onClick={onClick}
      disabled={disabled}
      className="sb-tool"
      style={{
        width: 24, height: 24, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        border: `1px solid ${active ? tint(k.blue, 45) : 'transparent'}`, borderRadius: 4,
        background: active ? tint(k.blue, 10) : 'transparent',
        color: active ? k.blue : k.dim,
        cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.45 : 1, padding: 0,
      }}
    >
      {children}
    </button>
  );
}

/**
 * A labelled control.
 *
 * The label is not decoration: an unlabelled pill reading "Derivatives" next to
 * one reading "1 Red" tells you nothing about which is the signal source and
 * which is the exit rule. Every control on this bar says what it governs.
 */
export function ToolbarControl({ label, hint, tone = k.dim, children }: {
  label: string;
  hint: string;
  tone?: string;
  children: React.ReactNode;
}) {
  return (
    <span title={hint} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
      <span style={{ fontSize: 8, fontWeight: 700, letterSpacing: '.07em', color: tone }}>{label}</span>
      {children}
    </span>
  );
}

/**
 * Separates server-side settings from local view filters.
 *
 * Left of it changes what is scanned or how trades exit, for everyone. Right of
 * it changes only what this browser shows. That distinction is worth a visible
 * line — it is the difference between filtering a list and changing a live
 * trading rule.
 */
export function ScopeDivider() {
  return (
    <span
      title="Left: engine settings, saved on the server and applied to trading. Right: local view filters that never change what is scanned."
      aria-hidden
      style={{ width: 1, alignSelf: 'stretch', minHeight: 14, background: k.border, flexShrink: 0, margin: '0 2px' }}
    />
  );
}

export function EngineToolbar({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px',
      borderBottom: `1px solid ${k.border}`, background: k.bg, flexWrap: 'wrap',
    }}>
      {children}
    </div>
  );
}
