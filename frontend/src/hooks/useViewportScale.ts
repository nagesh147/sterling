/**
 * Holds the document's scale in sync with the monitor and the user's setting.
 *
 * Mounted once, at the app root. The effect re-runs whenever any of the three
 * inputs change, which covers the settings side; the watcher it installs
 * covers the window side.
 */
import { useEffect } from 'react';
import { useStore } from '../store/useStore';
import { watchViewportScale } from '../styles/applyViewportScale';

export function useViewportScale(): void {
  const density = useStore((s) => s.density);
  const userScale = useStore((s) => s.zoomLevel);
  const autoFit = useStore((s) => s.autoFitDensity);

  useEffect(
    () => watchViewportScale(() => ({ density, userScale, autoFit })),
    [density, userScale, autoFit],
  );
}
