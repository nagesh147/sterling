import { useEffect, useMemo, useState, type MouseEvent } from "react";
import type { BuyContract } from "../../../lib/astro/tape";
import {
  bookQty,
  heldStrikeLabel,
  matchHeldOption,
  optionExchange,
  optionSideOf,
  planWindow,
  productForAction,
  type ContinueKind,
  type OpenPos,
  type OptionHit,
  type WindowPlan,
} from "../../../lib/astro/kiteContract";
import type { Underlying } from "../../../lib/astro/types";

const DEMO_KEY = "astro-demo-pos";

function loadDemo(): OpenPos[] {
  try {
    const raw = sessionStorage.getItem(DEMO_KEY);
    return raw ? (JSON.parse(raw) as OpenPos[]) : [];
  } catch {
    return [];
  }
}

function saveDemo(rows: OpenPos[]) {
  sessionStorage.setItem(DEMO_KEY, JSON.stringify(rows));
  window.dispatchEvent(new Event("astro-demo-pos"));
}

export function useDemoHeld(underlying: Underlying, prefer?: "CE" | "PE" | null) {
  const [rows, setRows] = useState(loadDemo);
  useEffect(() => {
    const on = () => setRows(loadDemo());
    window.addEventListener("astro-demo-pos", on);
    return () => window.removeEventListener("astro-demo-pos", on);
  }, []);
  return matchHeldOption(rows, underlying, prefer);
}

export type PlaceFn = (hit: OptionHit, product: "MIS" | "NRML", plan: WindowPlan) => void;
export type CloseFn = (pos: OpenPos) => void;
export type TrailFn = (pos: OpenPos, plan: WindowPlan) => void;

export function squareDemo(tradingsymbol: string) {
  saveDemo(loadDemo().filter((r) => r.tradingsymbol !== tradingsymbol));
}

export function OrderCell({
  buy,
  action,
  underlying,
  asOfIso,
  live = false,
  focus = true,
  instrument,
  resolving,
  connected = true,
  position,
  onBuy,
  onClose,
  onTrail,
  onBook,
}: {
  buy?: BuyContract;
  action: string;
  underlying: Underlying;
  asOfIso: string;
  live?: boolean;
  focus?: boolean;
  instrument?: OptionHit | null;
  resolving?: boolean;
  connected?: boolean;
  position?: (OpenPos & { optionSide?: "CE" | "PE" }) | null;
  onBuy?: PlaceFn;
  onClose?: CloseFn;
  onTrail?: TrailFn;
  onBook?: CloseFn;
}) {
  const side = buy?.side === "CE" || buy?.side === "PE" ? buy.side : null;
  const strike = buy?.strike ?? null;
  const [demoRows, setDemoRows] = useState(loadDemo);
  const [pending, setPending] = useState<ContinueKind | null>(null);

  useEffect(() => {
    const on = () => setDemoRows(loadDemo());
    window.addEventListener("astro-demo-pos", on);
    return () => window.removeEventListener("astro-demo-pos", on);
  }, []);

  const hit = useMemo<OptionHit | null>(() => {
    if (instrument) return instrument;
    if (onBuy) return null;
    if (!side || strike == null) return null;
    return {
      tradingsymbol: `${underlying}${strike}${side}`,
      exchange: optionExchange(underlying),
      strike,
      expiry: asOfIso,
      lot_size: underlying === "NIFTY" ? 65 : 15,
      last_price: 0,
      instrument_type: side,
    };
  }, [instrument, onBuy, side, strike, underlying, asOfIso]);

  const heldRaw = position ?? matchHeldOption(demoRows, underlying, side);
  const heldSide = heldRaw ? heldRaw.optionSide ?? optionSideOf(heldRaw.tradingsymbol) : null;
  const held = heldRaw && heldSide ? { ...heldRaw, optionSide: heldSide } : null;
  const mark = held ? heldStrikeLabel(held) : buy?.short && buy.short !== "—" ? buy.short : "";
  const plan = planWindow(action, buy?.side ?? "WAIT", held, mark);
  const product = productForAction(action);
  const stop = (e: MouseEvent) => e.stopPropagation();

  const go = (kind: ContinueKind) => (e: MouseEvent) => {
    stop(e);
    if (kind === "buy") {
      if (!hit) return;
      if (onBuy) {
        onBuy(hit, product, plan);
        return;
      }
      setPending("buy");
      return;
    }
    if (!held) return;
    if (kind === "close" && onClose) {
      onClose(held);
      return;
    }
    if (kind === "book" && onBook) {
      onBook(held);
      return;
    }
    if ((kind === "trail" || kind === "lock") && onTrail) {
      onTrail(held, plan);
      return;
    }
    setPending(kind);
  };

  if (plan.kind === "sit") return <span className="text-muted">—</span>;
  if (!focus) return <span className="text-muted">—</span>;

  const cls =
    plan.kind === "close" || plan.kind === "book"
      ? "ko-btn-close"
      : plan.kind === "trail" || plan.kind === "lock"
        ? "ko-btn-trail"
        : "ko-btn-buy";
  const disabled = plan.kind === "buy" && (resolving || (Boolean(onBuy) && (!connected || !hit)));

  return (
    <div className="ko-ord" onClick={stop}>
      <button type="button" className={cls} onClick={go(plan.kind)} disabled={disabled} title={plan.note} aria-label={plan.kind === "buy" ? `Buy ${plan.label}` : plan.label}>
        {resolving && plan.kind === "buy" ? "…" : plan.label}
      </button>
      {pending && (hit || held) ? (
        <div className="ko-ticket" role="dialog" aria-label={plan.label}>
          <p>
            {pending === "buy"
              ? `BUY ${hit?.lot_size ?? 1} ${hit?.tradingsymbol}`
              : pending === "book"
                ? `SELL ${bookQty(held!.quantity)} ${held!.tradingsymbol}`
                : pending === "close"
                  ? `SELL ${Math.abs(held!.quantity)} ${held!.tradingsymbol}`
                  : `GTT ${held?.tradingsymbol} · SL ${Math.abs(plan.slPct ?? 0)}%${plan.tgtPct ? ` · TGT ${plan.tgtPct}%` : ""}`}
            <span className="text-muted"> · {product}</span>
          </p>
          <p className="text-muted">{plan.note}</p>
          <div className="ko-ticket-act">
            <button
              type="button"
              className={pending === "close" || pending === "book" ? "ko-btn-close" : "ko-btn-buy"}
              onClick={(e) => {
                stop(e);
                if (pending === "buy" && hit) {
                  saveDemo([
                    ...loadDemo().filter((r) => r.tradingsymbol !== hit.tradingsymbol),
                    {
                      tradingsymbol: hit.tradingsymbol,
                      exchange: hit.exchange,
                      quantity: hit.lot_size,
                      product,
                      last_price: hit.last_price || 42,
                      average_price: hit.last_price || 42,
                    },
                  ]);
                } else if (pending === "close" && held) {
                  saveDemo(loadDemo().filter((r) => r.tradingsymbol !== held.tradingsymbol));
                } else if (pending === "book" && held) {
                  const sold = bookQty(held.quantity);
                  const left = Math.abs(held.quantity) - sold;
                  if (left <= 0) saveDemo(loadDemo().filter((r) => r.tradingsymbol !== held.tradingsymbol));
                  else {
                    saveDemo(loadDemo().map((r) => (r.tradingsymbol === held.tradingsymbol ? { ...r, quantity: left } : r)));
                  }
                }
                setPending(null);
              }}
            >
              Place
            </button>
            <button type="button" className="ko-link" onClick={(e) => { stop(e); setPending(null); }}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
