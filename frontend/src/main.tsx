import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles/globals.css';
import { App } from './App';
import { installScrollAutohide } from './utils/scrollAutohide';

installScrollAutohide();   // macOS-style: reveal scrollbars while scrolling, fade when idle

const root = document.getElementById('root');
if (!root) throw new Error('#root element not found');

createRoot(root).render(<App />);
