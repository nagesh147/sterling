import { create } from 'zustand';

// Bridges the "N live" running-signal count from the Sterling Kite Engine pane
// (which derives it from live LTP reconciliation) to the Kite footer status,
// which lives in a different component tree. The pane publishes; the footer reads.
interface LiveSignalCountState {
  count: number;
  setCount: (n: number) => void;
}

export const useLiveSignalCount = create<LiveSignalCountState>((set) => ({
  count: 0,
  setCount: (n) => set((s) => (s.count === n ? s : { count: n })),
}));
