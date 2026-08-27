import { describe, it, expect } from "vitest";
import { matchHeldOption, pickNearestOption, planWindow, productForAction, protectionPrices, ratchetProtection, searchQuery } from "./kiteContract";

describe("astro kite contract", () => {
  const rows = [
    { tradingsymbol: "NIFTY25827 24100PE", name: "NIFTY", exchange: "NFO", strike: 24100, expiry: "2026-08-27", lot_size: 65, instrument_type: "PE" },
    { tradingsymbol: "NIFTY25SEP24100PE", name: "NIFTY", exchange: "NFO", strike: 24100, expiry: "2026-09-30", lot_size: 65, instrument_type: "PE" },
    { tradingsymbol: "BANKNIFTY25827 24100PE", name: "BANKNIFTY", exchange: "NFO", strike: 24100, expiry: "2026-08-27", lot_size: 15, instrument_type: "PE" },
    { tradingsymbol: "NIFTY25827 24100CE", name: "NIFTY", exchange: "NFO", strike: 24100, expiry: "2026-08-27", lot_size: 65, instrument_type: "CE" },
  ];

  it("picks the nearest live Nifty PE, not Bank or a later month", () => {
    const hit = pickNearestOption(rows, "NIFTY", 24100, "PE", "2026-08-27");
    expect(hit?.tradingsymbol).toBe("NIFTY25827 24100PE");
  });

  it("treats any open Nifty PE as the held lot", () => {
    const pos = matchHeldOption(
      [
        { tradingsymbol: "BANKNIFTY25827 24100PE", quantity: 15, product: "MIS" },
        { tradingsymbol: "NIFTY25827 24100PE", quantity: 65, product: "MIS", last_price: 42 },
      ],
      "NIFTY",
      "PE",
    );
    expect(pos?.optionSide).toBe("PE");
    expect(pos?.quantity).toBe(65);
  });

  it("does not fire a second Buy when the next window is still PE", () => {
    const held = { optionSide: "PE", last_price: 42 };
    expect(planWindow("SCALP PE", "PE", null, "24,100 PE").kind).toBe("buy");
    expect(planWindow("SCALP PE", "PE", held, "24,100 PE").kind).toBe("trail");
    expect(planWindow("BUY CE", "CE", held, "24,100 PE").kind).toBe("close");
    expect(planWindow("BOOK PE", "PE", held, "24,100 PE").kind).toBe("book");
    expect(planWindow("AVOID", "WAIT", held, "24,100 PE").kind).toBe("lock");
    expect(planWindow("SCALP PE", "PE", held, "24,100 PE").label).toMatch(/Trail 24,100 PE · SL/);
  });

  it("ratchets a long-option stop up, never down", () => {
    const last = 50;
    const first = protectionPrices(last, -20, 30);
    const loose = protectionPrices(last, -40, 30);
    const down = ratchetProtection(last, loose, [first.sl, first.tgt ?? 0]);
    expect(down.sl).toBe(first.sl);
    expect(down.changed).toBe(false);
    const tight = protectionPrices(60, -20, 30);
    const up = ratchetProtection(60, { sl: tight.sl, tgt: tight.tgt }, [first.sl, first.tgt ?? 0]);
    expect(up.sl).toBeGreaterThanOrEqual(first.sl);
    expect(up.changed).toBe(true);
  });

  it("uses MIS on a scalp and NRML on a hold", () => {
    expect(productForAction("SCALP PE")).toBe("MIS");
    expect(productForAction("HOLD PE")).toBe("NRML");
    expect(searchQuery("NIFTY", 24100, "PE")).toBe("NIFTY 24100 PE");
  });
});
