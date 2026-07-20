import React, { useEffect, useMemo, useRef } from 'react';
import { AreaSeries, ColorType, createChart } from 'lightweight-charts';
import {
  useKiteCorporateActions,
  useKiteHoldings,
  useKiteIPOs,
  useKiteMargins,
  useKitePositions,
  useKiteQuote,
  useKiteStatus,
} from '../../hooks/useKite';
import { useCandles } from '../../hooks/useCandles';
import { MacReveal, MacSkeleton } from './