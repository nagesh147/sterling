import { useEffect, useMemo, useRef } from "react";
import { useKiteGtts, useKiteInstrumentSearch, useKitePositions, useKiteQuote, useKiteStatus, useModifyKiteGtt, usePlaceKiteGtt } from "../../../hooks/useKite";
import { useOrderWindowStore } from "../../../store/useOrderWindowStore";
import { notifyOrder } from "../../../store/useKiteNotifications";
import {
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
import type { Product } from "../orderTicket";

const ASTRO_LOT = "astro-managed-lot";
const gttOnce = new Set<string>();

export function rememberAstroLot(tradingsymbol: string) {
  try {
    sessionStorage.setItem(ASTRO_LOT, tradingsymbol);
  } catch {
    /* ignore */
  }
}

export function forgetAstroLot(tradingsymbol?: string) {
  try {
    if (!tradingsymbol || sessionStorage.getItem(ASTRO_LOT) === tradingsymbol) sessionStorage.removeItem(ASTRO_LOT);
  } catch {
    /* ignore */
  }
}

function astroLot(): string | null {
  try {
    return sessionStorage.getItem(ASTRO_LOT);
  } catch {
    return null;
  }
}

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

  const held = useMemo(() => {
    const mine = astroLot();
    if (!mine) return null;
    return matchHeldOption(
      (pos?.net ?? []).filter((p) => String(p.tradingsymbol ?? "").toUpperCase() === mine.toUpperCase()),
      underlying,
      side,
    );
  }, [pos, underlying, side]);

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
    const open = (use: OptionHit) => {
      rememberAstroLot(use.tradingsymbol);
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
    };
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
    forgetAstroLot(p.tradingsymbol);
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
  const held = useMemo(() => {
    const mine = astroLot();
    if (!mine) return null;
    return matchHeldOption(
      (pos?.net ?? []).filter((p) => String(p.tradingsymbol ?? "").toUpperCase() === mine.toUpperCase()),
      underlying,
      prefer,
    );
  }, [pos, underlying, prefer]);
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
      onClose: () => {
        forgetAstroLot(held.tradingsymbol);
        openOrderWindow({
          symbol: held.tradingsymbol,
          exchange: held.exchange,
          initialSide: held.quantity > 0 ? "SELL" : "BUY",
          initialQty: Math.abs(held.quantity),
          lastPrice: held.last_price,
          product: (held.product as Product) || "MIS",
          tag: "ASTRO",
        });
      },
    };
  }, [held, play, side, rows, nowMin, openOrderWindow]);
}

/** Trail GTT on the lot THIS desk bought. Never places orders — auto-order loops were a bug. */
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
  const high = useRef({ sym: "", px: 0 });
  const lot = astroLot();

  const held = useMemo(() => {
    if (!lot) return null;
    const mine = (pos?.net ?? []).filter((p) => String(p.tradingsymbol ?? "").toUpperCase() === lot.toUpperCase());
    return matchHeldOption(mine, underlying, null);
  }, [pos, underlying, lot]);

  const qsym = held ? [`${held.exchange}:${held.tradingsymbol}`] : [];
  const quote = useKiteQuote(qsym, connected && Boolean(held), 2_000);
  const livePx = Number((quote.data && Object.values(quote.data)[0] as { last_price?: number } | undefined)?.last_price) || 0;

  useEffect(() => {
    if (!armed || !connected || !held || !lot) return;
    if (held.tradingsymbol.toUpperCase() !== lot.toUpperCase()) return;
    if (Math.abs(held.quantity) <= 0) return;

    const more = runAhead(rows, held.optionSide, nowMin ?? 0);
    const action = live?.action ?? (more ? "WAIT" : "AVOID");
    const side = live?.side ?? "WAIT";
    const plan = planWindow(action, side, held, heldStrikeLabel(held), more);

    const raw = Math.max(livePx, held.last_price || 0);
    if (high.current.sym !== held.tradingsymbol) high.current = { sym: held.tradingsymbol, px: raw };
    high.current.px = Math.max(high.current.px, raw);
    const water = high.current.px;

    if (plan.kind === "close") {
      const note = `exit-note-${held.tradingsymbol}`;
      if (gttOnce.has(note)) return;
      gttOnce.add(note);
      notifyOrder({
        kind: "info",
        title: "Astro run over",
        message: `Close ${held.tradingsymbol} — same-side play ended. No auto order.`,
      });
      return;
    }

    if (plan.kind !== "trail" && plan.kind !== "lock" && plan.kind !== "book") return;
    if (!gtts.isFetched) return;
    if (!(water > 0) || plan.slPct == null) return;
    const proposed = proposedProtect(water, plan.slPct, plan.tgtPct, held.average_price, plan.kind);
    const existing = findGtt(gtts.data, held.tradingsymbol);
    const next = ratchetProtection(water, proposed, existing?.triggers ?? []);
    if (existing && !next.changed) return;
    const key = `gtt-${held.tradingsymbol}-${next.sl}-${next.tgt ?? 0}`;
    if (gttOnce.has(key)) return;
    gttOnce.add(key);
    const body = gttBody(held, water, next.sl, next.tgt);
    const onOk = () =>
      notifyOrder({
        kind: "info",
        title: existing ? "Astro trail" : "Astro stop",
        message: `${held.tradingsymbol} SL ₹${next.sl}${next.tgt != null ? ` · TGT ₹${next.tgt}` : ""}`,
      });
    if (existing) modifyGtt.mutate({ id: existing.id, ...body }, { onSuccess: onOk });
    else placeGtt.mutate(body, { onSuccess: onOk });
  }, [armed, connected, live, held, livePx, lot, rows, nowMin, gtts.isFetched, gtts.data, modifyGtt, placeGtt]);

  return null;
}
