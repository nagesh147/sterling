import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  DEFAULT_KITE_EXCHANGES,
  KITE_EXCHANGES,
  readKiteExchanges,
  writeKiteExchanges,
  type KiteExchange,
} from '../../utils/kiteExchanges';

const ORANGE = '#f06428';

export function KiteExchangeSettingsCard() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = React.useState<KiteExchange[]>(() => readKiteExchanges());

  const apply = (next: readonly