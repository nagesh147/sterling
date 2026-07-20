import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useKitePositions } from '../../hooks/useKite';
import type { WatchItem } from '../../types/kite';
import { k as t } from '../../styles/kiteUI';
import { SterlingWatchList } from './SterlingWatchList';

const WATCH_KEY = 'sterling.kite.watchlist.v1';
const MANUAL