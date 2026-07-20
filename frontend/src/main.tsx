import React, { useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/globals.css';
import './styles/performanceOverrides.css';
import './styles/kiteSignalTypography.css';
import { App } from './App';
import { installKiteDefaultPreferences } from './utils/kiteDefaultPreferences';
import { installScrollAutohide } from './utils/scrollAutohide';
import { installKiteChartTimezone } from './utils/kiteChartTimezone';

installKiteDefaultPreferences();
installScrollAutohide();   // macOS-style: reveal scrollbars while scrolling, fade when idle
installKiteChartTimezone(); // exchange candles and crosshair labels always render in IST

const root = document.getElementById('root');
if (!root) throw new Error('#root element not found');

function SterlingRoot() {
  useEffect(() => {
    const boot = document.getElementById('sterling-preboot');
    if (!boot) return;

    // Keep the static shell through the first committed React frame, then crossfade it.
    const frame = window.requestAnimationFrame(() => {
      boot.classList.add('sterling-preboot-leaving');
      const timer = window.setTimeout(() => boot.remove(), 180);
      boot.setAttribute('data-remove-timer', String(timer));
    });

    return () => {
      window.cancelAnimationFrame(frame);
      const timer = Number(boot.getAttribute('data-remove-timer'));
      if (Number.isFinite(timer)) window.clearTimeout(timer);
    };
  }, []);

  return <App />;
}

createRoot(root).render(<SterlingRoot />);

// Dev-only visual feedback overlay (agentation): click UI elements, annotate, and copy
// structured selector context to hand to the coding agent. Lazy dynamic import + the
// import.meta.env.DEV gate keep it fully tree-shaken out of production / real-money builds,
// and it mounts in its own DOM root so it can never interfere with the trading app tree.
if (import.meta.env.DEV) {
  void import('agentation').then(({ Agentation }) => {
    const host = document.createElement('div');
    host.id = 'agentation-root';
    document.body.appendChild(host);
    createRoot(host).render(<Agentation />);
  });
}
