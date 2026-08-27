import { useEffect, useMemo, useRef } from "react";
import { useKiteGtts, useKiteInstrumentSearch, useKitePositions, useKiteStatus, useModifyKiteGtt, usePlaceKiteGtt } from "../../../hooks/useKite";
import { useOrderWindowStore } from "../../../store/useOrderWindowStore";
import {
  findGtt,
  gttBody,
  heldStrikeLabel,
  matchHeldOption,
  pickNearestOption,
  planWindow,
  protectionPrices,
  ratchetProtection,
  searchQuery,
  type OpenPos,
  type OptionHit,
  type WindowPlan,
} from "../../../lib/astro/kiteContract";
import type { BuyContract } from "../../../lib/astro/tape";
import type { Underlying, WindowSlot } from "../../../lib/astro/types";
import { OrderCell } from "./OrderCell";
import type { Product } from "../orderTicket";

export function KiteOrderCell({
  buy,
  action,
  underlying,
  asOfIso,
  live = false,
  focus = true,
}: {
  buy?: BuyContract;
  action: string;
  underlying: Underlying;
  asOfIso: string;
  live?: boolean;
  focus?: boolean;
}) {
  const side = buy?.side === "CE" || buy?.side === "PE" ? buy.side : null;
  const strike = buy?.strike ?? null;
  const q = side && strike != null ? searchQuery(underlying, strike, side) : "";
  const search = useKiteInstrumentSearch(q);
  const status = useKiteStatus();
  const connected = Boolean(status.data?.connected);
  const { data: pos } = useKitePositions(connected);
  const gtts = useKiteGtts(connected);
  const placeGtt = usePlaceKiteGtt();
  const modifyGtt = useModifyKiteGtt();
  const openOrderWindow = useOrderWindowStore((s) => s.openOrderWindow);

  const instrument = useMemo<OptionHit | null>(() => {
    if (!side || strike == null || !search.data?.instruments) return null;
    return pickNearestOption(search.data.instruments, underlying, strike, side, asOfIso);
  }, [search.data, underlying, strike, side, asOfIso]);

  const held = useMemo(() => matchHeldOption(pos?.net ?? [], underlying, side), [pos, underlying, side]);

  const upsertTrail = (row: OpenPos, plan: WindowPlan) => {
    if (!(row.last_price > 0) || plan.slPct == null) return;
    const proposed = protectionPrices(row.last_price, plan.slPct, plan.tgtPct);
    const next = ratchetProtection(row.last_price, proposed, findGtt(gtts.data, row.tradingsymbol)?.triggers ?? []);
    if (!next.changed && findGtt(gtts.data, row.tradingsymbol)) return;
    const body = gttBody(row, row.last_price, next.sl, next.tgt);
    const existing = findGtt(gtts.data, row.tradingsymbol);
    if (existing) modifyGtt.mutate({ id: existing.id, ...body });
    else placeGtt.mutate(body);
  };

  const onBuy = (hit: OptionHit, product: "MIS" | "NRML", plan: WindowPlan) => {
    openOrderWindow({
      symbol: hit.tradingsymbol,
      exchange: hit.exchange,
      initialSide: "BUY",
      initialQty: hit.lot_size,
      lotSize: hit.lot_size,
      lastPrice: hit.last_price,
      product: product as Product,
      initialSlPct: plan.slPct ?? undefined,
      initialTgtPct: plan.tgtPct ?? undefined,
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

  const onBook = (p: OpenPos) => {
    const half = Math.max(1, Math.floor(Math.abs(p.quantity) / 2));
    openOrderWindow({
      symbol: p.tradingsymbol,
      exchange: p.exchange,
      initialSide: p.quantity > 0 ? "SELL" : "BUY",
      initialQty: half,
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
      live={live}
      focus={focus}
      instrument={instrument}
      resolving={Boolean(q) && search.isFetching && !instrument}
      connected={connected}
      position={held}
      onBuy={onBuy}
      onClose={onClose}
      onTrail={upsertTrail}
      onBook={onBook}
    />
  );
}

export function useAstroHolding(
  underlying: Underlying,
  play: string,
  side: "CE" | "PE" | "BOTH" | "WAIT",
) {
  const status = useKiteStatus();
  const connected = Boolean(status.data?.connected);
  const { data: pos } = useKitePositions(connected);
  const openOrderWindow = useOrderWindowStore((s) => s.openOrderWindow);
  const prefer = side === "CE" || side === "PE" ? side : null;
  const held = useMemo(() => matchHeldOption(pos?.net ?? [], underlying, prefer), [pos, underlying, prefer]);
  return useMemo(() => {
    if (!held) return null;
    const mark = heldStrikeLabel(held);
    const plan = planWindow(play, side, held, mark);
    if (plan.kind === "sit" || plan.kind === "buy") return null;
    return {
      mark,
      plan,
      onClose: () =>
        openOrderWindow({
          symbol: held.tradingsymbol,
          exchange: held.exchange,
          initialSide: held.quantity > 0 ? "SELL" : "BUY",
          initialQty: Math.abs(held.quantity),
          lastPrice: held.last_price,
          product: (held.product as Product) || "MIS",
          tag: "ASTRO",
        }),
    };
  }, [held, play, side, openOrderWindow]);
}

/** When the live window is still the same side, upgrade the GTT — do not add a lot. */
export function AstroTrailWatcher({
  live,
  underlying,
}: {
  live: WindowSlot | null;
  underlying: Underlying;
}) {
  const status = useKiteStatus();
  const connected = Boolean(status.data?.connected);
  const { data: pos } = useKitePositions(connected);
  const gtts = useKiteGtts(connected);
  const placeGtt = usePlaceKiteGtt();
  const modifyGtt = useModifyKiteGtt();
  const applied = useRef("");

  const held = useMemo(() => {
    const prefer = live?.side === "CE" || live?.side === "PE" ? live.side : null;
    return matchHeldOption(pos?.net ?? [], underlying, prefer);
  }, [pos, underlying, live?.side]);

  useEffect(() => {
    if (!connected || !live || !held) return;
    if (!gtts.isFetched) return;
    const mark = heldStrikeLabel(held);
    const plan = planWindow(live.action, live.side, held, mark);
    if (plan.kind !== "trail" && plan.kind !== "lock" && plan.kind !== "book") return;
    if (!(held.last_price > 0) || plan.slPct == null) return;
    const proposed = protectionPrices(held.last_price, plan.slPct, plan.tgtPct);
    const existing = findGtt(gtts.data, held.tradingsymbol);
    const next = ratchetProtection(held.last_price, proposed, existing?.triggers ?? []);
    if (existing && !next.changed) return;
    const key = `${live.from}-${held.tradingsymbol}-${next.sl}-${next.tgt ?? 0}`;
    if (applied.current === key) return;
    const body = gttBody(held, held.last_price, next.sl, next.tgt);
    applied.current = key;
    if (existing) modifyGtt.mutate({ id: existing.id, ...body });
    else placeGtt.mutate(body);
  }, [connected, live, held, gtts.isFetched, gtts.data, modifyGtt, placeGtt]);

  return null;
}
