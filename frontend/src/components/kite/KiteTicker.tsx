import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useKiteQuote } from '../../hooks/useKite';
import { useCandles } from '../../hooks/useCandles';
import { useTickerPins } from '../../store/useTickerPins';
import { InstrumentLabel } from './InstrumentLabel';
import { SignalMarker } from './SignalMarker';

// Keep the classic Chromium card treatment, but use the native UI stack so text
// stays crisp across Chrome/Chromium instead of depending on a downloaded webfont.
const TILE_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

const UP = '#