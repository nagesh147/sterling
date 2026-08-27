import { useEffect, useMemo, useState, type MouseEvent } from "react";
import type { BuyContract } from "../../../lib/astro/tape";
import {
  matchOpenPosition,
  optionExchange,
  productForAction,
  type OpenPos,
  type OptionHit,
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

export type PlaceFn = (hit: OptionHit, product: "MIS" | "NRML") => void;
export type CloseFn = (pos: OpenPos) => void;

export function OrderCell({
  buy,
  action,
  underlying,
  asOfIso,
  instrument,
  resolving,
  connected = true,
  position,
  onBuy,
  onClose,
}: {
  buy?: BuyContract;
  action: string;
  underlying: Underlying;
  asOfIso: string;
  instrument?: OptionHit | null;
  resolving?: boolean;
  connected?: boolean;
  position?: OpenPos | null;
  onBuy?: PlaceFn;
  onClose?: CloseFn;
}) {
  const side = buy?.side === "CE" || buy?.side === "PE" ? buy.side : null;
  const strike = buy?.strike ?? null;
  const canBuy = Boolean(side && strike && buy?.verb !== "SIT" && buy?.verb !== "BOOK");
  const [demoRows, setDemoRows] = useState(loadDemo);
  const [pending, setPending] = useState<"buy" | "close" | null>(null);

  useEffect(() => {
    const on = () => setDemoRows(loadDemo());
    window.addEventListener("astro-demo-pos", on);
    return () => window.removeEventListener("astro-demo-pos", on);
  }, []);

  const hit = useMemo<OptionHit | null>(() => {
    if (instrument) return instrument;
    if (onBuy) return null;
    if (!canBuy || !side || strike == null) return null;
    return {
      tradingsymbol: `${underlying}${strike}${side}`,
      exchange: optionExchange(underlying),
      strike,
      expiry: asOfIso,
      lot_size: underlying === "NIFTY" ? 65 : 15,
      last_price: 0,
      instrument_type: side,
    };
  }, [instrument, onBuy, canBuy, side, strike, underlying, asOfIso]);

  const open =
    position ?? (side && strike != null ? matchOpenPosition(demoRows, underlying, strike, side) : null);
  const product = productForAction(action);
  const stop = (e: MouseEvent) => e.stopPropagation();

  const goBuy = (e: MouseEvent) => {
    stop(e);
    if (!hit) return;
    if (onBuy) {
      onBuy(hit, product);
      return;
    }
    setPending("buy");
  };

  const goClose = (e: MouseEvent) => {
    stop(e);
    if (!open) return;
    if (onClose) {
      onClose(open);
      return;
    }
    setPending("close");
  };

  if (!canBuy && !open) {
    if (buy && buy.verb !== "SIT" && buy.short && buy.short !== "—") {
      return <span className="text-muted">{buy.short}</span>;
    }
    return <span className="text-muted">—</span>;
  }

  const mark = buy?.short && buy.short !== "—" ? buy.short : side && strike != null ? `${strike} ${side}` : "";
  const buyLabel = mark ? `Buy ${mark}` : "Buy";
  const closeLabel = mark ? `Close ${mark}` : "Close";

  return (
    <div className="ko-ord" onClick={stop}>
      {open ? (
        <button type="button" className="ko-btn-close" onClick={goClose} aria-label={closeLabel}>
          {closeLabel}
        </button>
      ) : (
        <button
          type="button"
          className="ko-btn-buy"
          onClick={goBuy}
          disabled={resolving || (Boolean(onBuy) && (!connected || !hit))}
          aria-label={buyLabel}
        >
          {resolving ? "…" : buyLabel}
        </button>
      )}
      {pending && hit ? (
        <div className="ko-ticket" role="dialog" aria-label="Place order">
          <p>
            {pending === "close" ? "SELL" : "BUY"} {pending === "close" ? Math.abs(open?.quantity ?? hit.lot_size) : hit.lot_size}{" "}
            {pending === "close" ? open?.tradingsymbol : hit.tradingsymbol}
            <span className="text-muted">
              {" "}
              · {pending === "close" ? open?.product ?? product : product} · {hit.exchange}
            </span>
          </p>
          <div className="ko-ticket-act">
            <button
              type="button"
              className={pending === "close" ? "ko-btn-close" : "ko-btn-buy"}
              onClick={(e) => {
                stop(e);
                if (pending === "buy") {
                  saveDemo([
                    ...loadDemo().filter((r) => r.tradingsymbol !== hit.tradingsymbol),
                    {
                      tradingsymbol: hit.tradingsymbol,
                      exchange: hit.exchange,
                      quantity: hit.lot_size,
                      product,
                      last_price: hit.last_price,
                    },
                  ]);
                } else if (open) {
                  saveDemo(loadDemo().filter((r) => r.tradingsymbol !== open.tradingsymbol));
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
