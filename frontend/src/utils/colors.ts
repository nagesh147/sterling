import { c as ui } from '../styles/terminalUI';

/** Single source of truth for signal state colors — used by AlertsPanel and InstrumentDetailCard */
export const STATE_COLOR: Record<string, string> = {
  ENTRY_ARMED_PULLBACK:     ui.blue,
  ENTRY_ARMED_CONTINUATION: ui.cyan,
  CONFIRMED_SETUP_ACTIVE:   ui.amber,
  EARLY_SETUP_ACTIVE:       ui.amber,
};

export const STATE_SHORT: Record<string, string> = {
  ENTRY_ARMED_PULLBACK:     'ARMED',
  ENTRY_ARMED_CONTINUATION: 'ARMED',
  CONFIRMED_SETUP_ACTIVE:   'CONFIRMED',
  EARLY_SETUP_ACTIVE:       'FORMING',
  FILTERED:                 'FILTERED',
  IDLE:                     'IDLE',
};

/** Mode badge colours — single source of truth for scalping/intraday/swing/positional/all */
export const MODE_COLOR: Record<string, string> = {
  scalping:   '#ff7f6e',
  intraday:   '#f0c040',
  swing:      'var(--accent)',
  positional: '#aa88ff',
  all:        '#88ccff',
};
