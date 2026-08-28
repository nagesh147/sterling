import { create } from 'zustand';
import type { ScannableEngine } from '../hooks/useScanAllStrategies';

/**
 * Which strategy a manual re-scan is on right now.
 *
 * Only SuperTrend publishes a live scan feed — `/activity` gives its `scanning`
 * flag and the contract it is reading. The other four have scan endpoints and
 * nothing that reports progress, so while the re-scan button works through them
 * the platform had no way to say which one was running: the status line showed
 * SuperTrend's last contract and then fell back to "AUTO", which reads as
 * "nothing is happening" in the middle of a five-engine sweep.
 *
 * The fan-out is sequential and lives in one function, so that function can just
 * say where it is. Deliberately NOT persisted: it describes a press that is
 * happening now, and a reload means it is not happening any more.
 */
interface ScanActivityState {
  /** The engine currently being scanned by a manual re-scan, if any. */
  current: ScannableEngine | null;
  setCurrent: (engine: ScannableEngine | null) => void;
}

export const useScanActivity = create<ScanActivityState>()((set) => ({
  current: null,
  setCurrent: (current) => set({ current }),
}));

export default useScanActivity;
