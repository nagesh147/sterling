import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useKitePositions, useSyncKiteWatchlist } from '../../hooks/useKite';
import type { WatchItem } from '../../types/kite';
import { k as t } from '../../styles/kiteUI';
import { SterlingWatchList } from './SterlingWatchList';

const WATCH_KEY = 'sterling.kite.watchlist.v1';
const MANUAL_EMPTY_KEY = 'sterling.kite.watchlist.manual-empty.v1';
const MAX_WATCH_ITEMS = 50;

function readWatchlist(): WatchItem[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(WATCH_KEY) || '[]');
    return Array.isArray(parsed) ? parsed :