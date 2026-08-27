import { useEffect, useMemo, useRef } from "react";
import { useDeleteKiteGtt, useKiteGtts, useKiteInstrumentSearch, useKitePositions, useKiteQuote, useKiteStatus, useModifyKiteGtt, usePlaceKiteGtt, usePlaceKiteOrder } from "../../../hooks/useKite";
import { useOrderWindowStore } from "../../../store/useOrderWindowStore";
import { notifyOrder } from "../../../store/useKiteNotifications";
import {
  bookQty,
  findGtt,
  gttBody,
  heldStrikeLabel,
  matchHeldOption,
  optionPnl,
  pickNearestOption,
  planWindow,
  proposedProtect,
  ratchetProtection,
  runAhead,
  searchQuery,
  type OpenPos,
  type OptionHit,
  type WindowPlan,
} from "../../../lib/astro/kiteContract";
import type { BuyContract } from "../../../lib/astro/tape";
import type { Underlying, WindowSlot } from "../../../lib/astro/types";
import { OrderCell } from "./OrderCell";
import { buildOrderBody, type Product } from "../orderTicket";

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
    const proposed = proposedProtect(row.last_price, plan.slPct, plan.tgtPct, row.average_price, plan.kind);
    const next = ratchetProtection(row.last_price, proposed, findGtt(gtts.data, row.tradingsymbol)?.triggers ?? []);
    if (!next.changed && findGtt(gtts.data, row.tradingsymbol)) return;
    const body = gttBody(row, row.last_price, next.sl, next.tgt);
    const existing = findGtt(gtts.data, row.tradingsymbol);
    if (existing) modifyGtt.mutate({ id: existing.id, ...body });
    else placeGtt.mutate(body);
  };

  const onBuy = (hit: OptionHit, product: "MIS" | "NRML", plan: WindowPlan) => {
    const open = (use: OptionHit) =>
      openOrderWindow({
        symbol: use.tradingsymbol,
        exchange: use.exchange,
        initialSide: "BUY",
        initialQty: use.lot_size,
        lotSize: use.lot_size,
        lastPrice: use.last_price,
        product: product as Product,
        initialSlPct: plan.slPct ?? -20,
        initialTgtPct: plan.tgtPct ?? 30,
        tag: "ASTRO",
      });
    if (instrument) {
      open(instrument);
      return;
    }
    const fromCache = pickNearestOption(search.data?.instruments ?? [], underlying, hit.strike, hit.instrument_type, "0000-01-01");
    if (fromCache) {
      open(fromCache);
      return;
    }
    void search.refetch().then((res) => {
      const picked = pickNearestOption(res.data?.instruments ?? [], underlying, hit.strike, hit.instrument_type, "0000-01-01");
      if (picked) {
        open(picked);
        return;
      }
      notifyOrder({ kind: "error", title: "Astro buy", message: "Could not resolve the option. Connect Kite and retry." });
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
    const half = bookQty(p.quantity);
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
  rows: WindowSlot[] = [],
  nowMin: number | null = null,
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
    const more = runAhead(rows, held.optionSide, nowMin ?? 0);
    const plan = planWindow(play, side, held, mark, more);
    if (plan.kind === "sit" || plan.kind === "buy") return null;
    return {
      mark,
      plan,
      pnl: optionPnl(held),
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
  }, [held, play, side, rows, nowMin, openOrderWindow]);
}

/** One lot: trail while the same play continues, wait through a gap, auto-exit when the run ends. */
export function AstroTrailWatcher({
  live,
  rows = [],
  underlying,
  nowMin = null,
  armed = true,
}: {
  live: WindowSlot | null;
  rows?: WindowSlot[];
  underlying: Underlying;
  nowMin?: number | null;
  armed?: boolean;
}) {
  const status = useKiteStatus();
  const connected = Boolean(status.data?.connected);
  const { data: pos } = useKitePositions(connected);
  const gtts = useKiteGtts(connected);
  const placeGtt = usePlaceKiteGtt();
  const modifyGtt = useModifyKiteGtt();
  const deleteGtt = useDeleteKiteGtt();
  const placeOrder = usePlaceKiteOrder();
  const applied = useRef("");
  const high = useRef({ sym: "", px: 0 });

  const held = useMemo(() => matchHeldOption(pos?.net ?? [], underlying, null), [pos, underlying]);
  const qsym = held ? [`${held.exchange}:${held.tradingsymbol}`] : [];
  const quote = useKiteQuote(qsym, connected && Boolean(held), 2_000);
  const livePx = Number((quote.data && Object.values(quote.data)[0] as { last_price?: number } | undefined)?.last_price) || 0;

  useEffect(() => {
    if (!armed || !connected || !held) return;
    const inCash = nowMin != null && nowMin >= 555 && nowMin < 930;
    const more = runAhead(rows, held.optionSide, nowMin ?? 0);
    const action = live?.action ?? (more ? "WAIT" : "AVOID");
    const side = live?.side ?? "WAIT";
    const mark = heldStrikeLabel(held);
    const plan = planWindow(action, side, held, mark, more);

    const raw = Math.max(livePx, held.last_price || 0);
    if (high.current.sym !== held.tradingsymbol) high.current = { sym: held.tradingsymbol, px: raw };
    high.current.px = Math.max(high.current.px, raw);
    const water = high.current.px;

    if (plan.kind === "close") {
      if (!inCash || !live) return;
      const key = `exit-${held.tradingsymbol}`;
      if (applied.current === key || placeOrder.isPending) return;
      applied.current = key;
      const gtt = findGtt(gtts.data, held.tradingsymbol);
      placeOrder.mutate(
        buildOrderBody({
          tradingsymbol: held.tradingsymbol,
          exchange: held.exchange,
          side: held.quantity > 0 ? "SELL" : "BUY",
          quantity: Math.abs(held.quantity),
          product: (held.product as Product) || "MIS",
          orderType: "MARKET",
          tag: "ASTRO",
        }),
        {
          onSuccess: () => {
            notifyOrder({ kind: "complete", title: "Astro exit", message: `${held.tradingsymbol} — run over` });
            if (gtt) deleteGtt.mutate(gtt.id);
          },
          onError: () => {
            applied.current = "";
          },
        },
      );
      return;
    }

    if (plan.kind === "book") {
      const half = bookQty(held.quantity);
      if (half > 0 && half < Math.abs(held.quantity)) {
        const key = `book-${live?.from ?? "x"}-${held.tradingsymbol}`;
        if (applied.current !== key && !placeOrder.isPending) {
          applied.current = key;
          placeOrder.mutate(
            buildOrderBody({
              tradingsymbol: held.tradingsymbol,
              exchange: held.exchange,
              side: held.quantity > 0 ? "SELL" : "BUY",
              quantity: half,
              product: (held.product as Product) || "MIS",
              orderType: "MARKET",
              tag: "ASTRO",
            }),
            {
              onSuccess: () => notifyOrder({ kind: "complete", title: "Astro book", message: `Sold ${half} ${held.tradingsymbol}` }),
              onError: () => {
                applied.current = "";
              },
            },
          );
        }
      }
    }

    if (plan.kind !== "trail" && plan.kind !== "lock" && plan.kind !== "book") return;
    if (!gtts.isFetched) return;
    if (!(water > 0) || plan.slPct == null) return;
    const proposed = proposedProtect(water, plan.slPct, plan.tgtPct, held.average_price, plan.kind);
    const existing = findGtt(gtts.data, held.tradingsymbol);
    const next = ratchetProtection(water, proposed, existing?.triggers ?? []);
    if (existing && !next.changed) return;
    const key = `trail-${held.tradingsymbol}-${next.sl}-${next.tgt ?? 0}`;
    if (applied.current === key) return;
    const body = gttBody(held, water, next.sl, next.tgt);
    applied.current = key;
    const onOk = () =>
      notifyOrder({
        kind: "info",
        title: existing ? "Astro trail" : "Astro stop",
        message: `${held.tradingsymbol} SL ₹${next.sl}${next.tgt != null ? ` · TGT ₹${next.tgt}` : ""}`,
      });
    if (existing) modifyGtt.mutate({ id: existing.id, ...body }, { onSuccess: onOk });
    else placeGtt.mutate(body, { onSuccess: onOk });
  }, [armed, connected, live, held, livePx, rows, nowMin, gtts.isFetched, gtts.data, modifyGtt, placeGtt, placeOrder, deleteGtt]);

  return null;
}
