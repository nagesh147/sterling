import { create } from 'zustand';
import type { Product } from '../components/kite/orderTicket';

export interface OrderWindowOptions {
  symbol: string;                       // tradingsymbol only, e.g. "INFY" (no exchange prefix)
  exchange: string;                     // NSE/BSE/NFO/BFO/...
  initialSide: 'BUY' | 'SELL';
  initialQty?: number;                  // total quantity (lots × lot_size), not lot count
  lastPrice?: number;
  lotSize?: number;                     // 1 for equity; contract lot for F&O
  product?: Product;                    // preselect MIS/CNC/NRML (e.g. to square off a position)
  initialSlPct?: number;                // prefilled Stoploss % for protective GTT
  initialTgtPct?: number;               // prefilled Target % for protective GTT
  tag?: string;                         // ≤20-char audit tag
  onPlaced?: (orderId: string) => void; // fired after a successful placement
}

interface OrderWindowState {
  isOpen: boolean;
  options: OrderWindowOptions | null;
  openOrderWindow: (options: OrderWindowOptions) => void;
  closeOrderWindow: () => void;
}

export const useOrderWindowStore = create<OrderWindowState>((set) => ({
  isOpen: false,
  options: null,
  openOrderWindow: (options) => set({ isOpen: true, options }),
  closeOrderWindow: () => set({ isOpen: false, options: null }),
}));
