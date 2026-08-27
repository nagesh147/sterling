import { describe, it, expect } from "vitest";
import { bookQty, matchHeldOption, pickNearestOption, planWindow, productForAction, proposedProtect, protectionPrices, ratchetProtection, searchQuery } from "./kiteContract";

describe("astro kite contract", () => {
  const rows = [
    { tradingsymbol: "NIFTY25827 24100PE", name: "NIFTY", exchange: "NFO", strike: 24100, expiry: "2026-08-27", lot_size: 65, instrument_type: "PE" },
    { tradingsymbol: "NIFTY25SEP24100PE", name: "NIFTY", exchange: "NFO", strike: 24100, expiry: "2026-09-30", lot_size: 65, instrument_type: "PE" },
    { tradingsymbol: "BANKNIFTY25827 24100PE", name: "BANKNIFTY", exchange: "NFO", strike: 24100, expiry: "2026-08-27", lot_size: 15, instrument_type: "PE" },
    { tradingsymbol: "NIFTY25827 24100CE", name: "NIFTY", exchange: "NFO", strike: 24100, expiry: "2026-08-27", lot_size: 65, instrument_type: "CE" },
  ];

  it("picks the nearest live Nifty PE", () => {
    expect(pickNearestOption(rows, "NIFTY", 24100, "PE", "2026-08-27")?.tradingsymbol).toBe("NIFTY25827 24100PE");
  });

  it("does not fire a second Buy when the next window is still PE", () => {
    const held = { optionSide: "PE" as const, last_price: 42 };
    expect(planWindow("SCALP PE", "PE", null, "24,100 PE").kind).toBe("buy");
    expect(planWindow("SCALP PE", "PE", null, "24,100 PE").label).toBe("24,100 PE");
    expect(planWindow("SCALP PE", "PE", held, "24,100 PE").kind).toBe("trail");
    expect(planWindow("BUY CE", "CE", held, "24,100 PE").kind).toBe("close");
    expect(planWindow("AVOID", "WAIT", held, "24,100 PE").kind).toBe("lock");
  });

  it("locks a winner to cost", () => {
    expect(proposedProtect(80, -12, null, 50, "lock").sl).toBe(50);
    expect(proposedProtect(40, -12, null, 50, "lock").sl).toBe(protectionPrices(40, -12, null).sl);
  });

  it("books half a lot only when there are two", () => {
    expect(bookQty(65, 65)).toBe(65);
    expect(bookQty(130, 65)).toBe(65);
  });

  it("ratchets a long-option stop up, never down", () => {
    const first = protectionPrices(50, -20, 30);
    const loose = protectionPrices(50, -40, 30);
    const down = ratchetProtection(50, loose, [first.sl, first.tgt ?? 0]);
    expect(down.sl).toBe(first.sl);
    expect(down.changed).toBe(false);
  });

  it("uses MIS on a scalp", () => {
    expect(productForAction("SCALP PE")).toBe("MIS");
    expect(searchQuery("NIFTY", 24100, "PE")).toBe("NIFTY 24100 PE");
    expect(matchHeldOption([{ tradingsymbol: "NIFTY25827 24100PE", quantity: 65 }], "NIFTY", "PE")?.optionSide).toBe("PE");
  });
});
