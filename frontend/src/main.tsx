import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles/globals.css';
import { App } from './App';
import { installScrollAutohide } from './utils/scrollAutohide';

installScrollAutohide();   // macOS-style: reveal scrollbars while scrolling, fade when idle

const root = document.getElementById('root');
if (!root) throw new Error('#root element not found');

createRoot(root).render(<App />);

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
