import { create } from 'zustand';

// ─── Signal markers (✝ best R:R, ▲ best delta) shared across panes ──────────────
// The Sterling Kite Engine rows compute, per signal, which option leg is the best
// reward:risk (✝) and which has the highest delta (▲). Those same markers should
// follow the instrument anywhere it appears — the market watchlist and the ticker
// — so a user who pins/adds a marked contract sees the same ✝/▲.
//
// Each SignalCard publishes its markers keyed by its signal token (so re-renders
// replace cleanly and unmounts remove them). The flat `markers` map — keyed by the
// full `EXCHANGE:tradingsymbol` symbol (the same string the watchlist/ticker use)
// — is what consumers read.

export interface Marker { rr?: boolean; delta?: boolean }

interface SignalMarkersState {
  /** token -> { fullSymbol -> Marker } */
  byRow: Record<string, Record<string, Marker>>;
  /** flattened fullSymbol -> Marker (OR-merged across rows) */
  markers: Record<string, Marker>;
  publish: (rowKey: string, entries: Record<string, Marker>) => void;
  clear: (rowKey: string) => void;
}

function sameEntries(a: Record<string, Marker> | undefined, b: Record<string, Marker>): boolean {
  if (!a) return false;
  const ak = Object.keys(a);
  const bk = Object.keys(b);
  if (ak.length !== bk.length) return false;
  for (const k of ak) {
    if (!b[k] || a[k].rr !== b[k].rr || a[k].delta !== b[k].delta) return false;
  }
  return true;
}

function flatten(byRow: Record<string, Record<string, Marker>>): Record<string, Marker> {
  const out: Record<string, Marker> = {};
  for (const row of Object.values(byRow)) {
    for (const [sym, m] of Object.entries(row)) {
      const cur = out[sym];
      out[sym] = { rr: cur?.rr || m.rr, delta: cur?.delta || m.delta };
    }
  }
  return out;
}

export const useSignalMarkers = create<SignalMarkersState>((set) => ({
  byRow: {},
  markers: {},
  publish: (rowKey, entries) => set((s) => {
    if (sameEntries(s.byRow[rowKey], entries)) return s;
    const byRow = { ...s.byRow, [rowKey]: entries };
    return { byRow, markers: flatten(byRow) };
  }),
  clear: (rowKey) => set((s) => {
    if (!s.byRow[rowKey]) return s;
    const byRow = { ...s.byRow };
    delete byRow[rowKey];
    return { byRow, markers: flatten(byRow) };
  }),
}));
