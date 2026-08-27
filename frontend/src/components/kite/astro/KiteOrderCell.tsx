import { useMemo } from "react";
import { useKiteInstrumentSearch, useKitePositions, useKiteStatus } from "../../../hooks/useKite";
import { useOrderWindowStore } from "../../../store/useOrderWindowStore";
import { matchOpenPosition, pickNearestOption, searchQuery, type OptionHit, type OpenPos } from "../../../lib/astro/kiteContract";
import type { BuyContract } from "../../../lib/astro/tape";
import type { Underlying } from "../../../lib/astro/types";
import { OrderCell } from "./OrderCell";
import type { Product } from "../orderTicket";

export function KiteOrderCell({
  buy,
  action,
  underlying,
  asOfIso,
}: {
  buy?: BuyContract;
  action: string;
  underlying: Underlying;
  asOfIso: string;
}) {
  const side = buy?.side === "CE" || buy?.side === "PE" ? buy.side : null;
  const strike = buy?.strike ?? null;
  const q = side && strike != null ? searchQuery(underlying, strike, side) : "";
  const search = useKiteInstrumentSearch(q);
  const status = useKiteStatus();
  const connected = Boolean(status.data?.connected);
  const { data: pos } = useKitePositions(connected);
  const openOrderWindow = useOrderWindowStore((s) => s.openOrderWindow);

  const instrument = useMemo<OptionHit | null>(() => {
    if (!side || strike == null || !search.data?.instruments) return null;
    return pickNearestOption(search.data.instruments, underlying, strike, side, asOfIso);
  }, [search.data, underlying, strike, side, asOfIso]);

  const position = useMemo<OpenPos | null>(() => {
    if (!side || strike == null) return null;
    return matchOpenPosition(pos?.net ?? [], underlying, strike, side);
  }, [pos, underlying, strike, side]);

  const onBuy = (hit: OptionHit, product: "MIS" | "NRML") => {
    openOrderWindow({
      symbol: hit.tradingsymbol,
      exchange: hit.exchange,
      initialSide: "BUY",
      initialQty: hit.lot_size,
      lotSize: hit.lot_size,
      lastPrice: hit.last_price,
      product: product as Product,
      tag: "ASTRO",
    });
  };

  const onClose = (p: OpenPos) => {
    openOrderWindow({
      symbol: p.tradingsymbol,
      exchange: p.exchange,
      initialSide: p.quantity > 0 ? "SELL" : "BUY",
      initialQty: Math.abs(p.quantity),
      lastPrice: p.last_price,
      product: (p.product as Product) || "MIS",
      tag: "ASTRO",
    });
  };

  return (
    <OrderCell
      buy={buy}
      action={action}
      underlying={underlying}
      asOfIso={asOfIso}
      instrument={instrument}
      resolving={Boolean(q) && search.isFetching && !instrument}
      connected={connected}
      position={position}
      onBuy={onBuy}
      onClose={onClose}
    />
  );
}
