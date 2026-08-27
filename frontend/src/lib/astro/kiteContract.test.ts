import { describe, it, expect } from "vitest";
import { matchOpenPosition, pickNearestOption, productForAction, searchQuery } from "./kiteContract";

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
    expect(hit?.lot_size).toBe(65);
  });

  it("skips an expiry that already died", () => {
    const hit = pickNearestOption(rows, "NIFTY", 24100, "PE", "2026-08-28");
    expect(hit?.tradingsymbol).toBe("NIFTY25SEP24100PE");
  });

  it("does not mix Nifty into a Bank Nifty search", () => {
    const hit = pickNearestOption(rows, "BANKNIFTY", 24100, "PE", "2026-08-27");
    expect(hit?.tradingsymbol).toBe("BANKNIFTY25827 24100PE");
  });

  it("matches an open long on that strike", () => {
    const pos = matchOpenPosition(
      [
        { tradingsymbol: "BANKNIFTY25827 24100PE", quantity: 15, product: "MIS" },
        { tradingsymbol: "NIFTY25827 24100PE", quantity: 65, product: "MIS", last_price: 42 },
      ],
      "NIFTY",
      24100,
      "PE",
    );
    expect(pos?.quantity).toBe(65);
    expect(pos?.tradingsymbol).toBe("NIFTY25827 24100PE");
  });

  it("uses MIS on a scalp and NRML on a hold", () => {
    expect(productForAction("SCALP PE")).toBe("MIS");
    expect(productForAction("HOLD PE")).toBe("NRML");
    expect(searchQuery("NIFTY", 24100, "PE")).toBe("NIFTY 24100 PE");
  });
});
