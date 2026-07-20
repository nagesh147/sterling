import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useKitePositions, useSyncKiteWatchlist } from '../../hooks/useKite';
import type { WatchItem } from '../../types/kite';
import { k as t } from '../../styles/kiteUI';
import { SterlingWatchList } from './SterlingWatchList';

const WATCH_KEY = 'sterling.kite.watchlist.v1';
const MANUAL_EMPTY_KEY = 'sterling.kite.watchlist.manual-empty.v1