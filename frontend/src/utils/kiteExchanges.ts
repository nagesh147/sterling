export const KITE_EXCHANGES = ['NSE', 'NFO', 'BSE', 'BFO', 'CDS', 'BCD', 'MCX'] as const;

export type KiteExchange = typeof KITE_EXCHANGES[number];

// "NSE market" means cash equities/indices on NSE plus its F&O segment, NFO.
// This preserves the options-first Sterling workflow while excluding BSE/BFO by default.
export const DEFAULT_KITE_EXCHANGES: KiteExchange[] = ['NSE', 'NFO'];
export const KITE_SETTINGS_STORAGE_KEY = 'kite-settings';

const EXCHANGE_SET = new Set<string>(