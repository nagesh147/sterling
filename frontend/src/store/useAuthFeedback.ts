import { create } from 'zustand';

// Drives the global Kite auth overlay (the mac-style "connecting…" spinner and
// the success checkmark). Mutation hooks and the connection watcher push phase
// changes here; <KiteAuthOverlay /> renders them. Kept as a non-hook store so it
// can be driven from React Query callbacks that run outside the render tree.
export type AuthPhase = 'idle' | 'connecting' | 'success';

interface State {
  phase: AuthPhase;
  /** Optional line shown under the spinner / checkmark. */
  label: string;
  setPhase: (phase: AuthPhase, label?: string) => void;
}

export const useAuthFeedback = create<State>((set) => ({
  phase: 'idle',
  label: '',
  setPhase: (phase, label = '') => set({ phase, label }),
}));

let safetyTimer: number | undefined;

// Non-hook accessors for use inside mutation callbacks.
export const authConnecting = (label = 'Connecting to Kite…') => {
  useAuthFeedback.getState().setPhase('connecting', label);
  // Safety net: never let the "connecting" overlay hang if the status poll
  // somehow never flips to connected (network hiccup, slow refetch).
  window.clearTimeout(safetyTimer);
  safetyTimer = window.setTimeout(() => {
    if (useAuthFeedback.getState().phase === 'connecting') {
      useAuthFeedback.getState().setPhase('idle');
    }
  }, 12000);
};

export const authSuccess = (label = 'Connected') => {
  window.clearTimeout(safetyTimer);
  useAuthFeedback.getState().setPhase('success', label);
  // Auto-clear the success flourish after it has played.
  window.setTimeout(() => {
    if (useAuthFeedback.getState().phase === 'success') {
      useAuthFeedback.getState().setPhase('idle');
    }
  }, 1600);
};

export const authIdle = () => {
  window.clearTimeout(safetyTimer);
  useAuthFeedback.getState().setPhase('idle');
};
