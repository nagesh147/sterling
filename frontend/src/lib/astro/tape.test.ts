import { describe, it, expect } from "vitest";
import { buyContract, gradeSlot, parseYahooChart, roundStrike, summariseTape, windowOhlc } from "./tape";
import { utcFromIstParts } from "./time";
import type { WindowSlot } from "./types";

function bar(h: number, m: number, o: number, c: number, hi?: number, lo?: number) {
  const t = Math.floor(utcFromIstParts(2026, 8, 26, h, m, 0).getTime() / 1000);
  return { t, o, h: hi ?? Math.max(o, c), l: lo ?? Math.min(o, c), c };
}

const slot = (
  fromMin: number,
  toMin: number,
  side: WindowSlot["side"],
  action: WindowSlot["action"],
): Pick<WindowSlot, "fromMin" | "toMin" | "side" | "action"> => ({
  fromMin,
  toMin,
  side,
  action,
});

describe("tape overlay", () => {
  const tape = {
    iso: "2026-08-26",
    underlying: "NIFTY" as const,
    symbol: "^NSEI",
    prevClose: 24334.55,
    sessionOpen: 24341.95,
    source: "test",
    bars: [
      bar(9, 15, 24343, 24318, 24355, 24310),
      bar(9, 20, 24318, 24350, 24362, 24318),
      bar(9, 40, 24350, 24372, 24376, 24350),
      bar(9, 45, 24372, 24343, 24378, 24333),
      bar(10, 10, 24343, 24343, 24348, 24333),
    ],
  };

  it("aggregates a 30-min window from 5-min bars", () => {
    const w = windowOhlc(tape.bars, "2026-08-26", 9 * 60 + 15, 9 * 60 + 45);
    expect(w).toBeTruthy();
    expect(w?.open).toBe(24343);
    expect(w?.close).toBe(24372);
    expect(w?.high).toBe(24376);
  });

  it("marks CE hit when the window closes up, PE miss", () => {
    const ce = gradeSlot(slot(555, 585, "CE", "BUY CE"), tape, 16 * 60, false);
    const pe = gradeSlot(slot(555, 585, "PE", "SCALP PE"), tape, 16 * 60, false);
    expect(ce.kind).toBe("HIT");
    expect(pe.kind).toBe("MISS");
  });

  it("sits WAIT without counting a miss", () => {
    const g = gradeSlot(slot(555, 585, "WAIT", "WAIT"), tape, 16 * 60, false);
    expect(g.kind).toBe("SIT");
  });

  it("does not grade a future slot", () => {
    const g = gradeSlot(slot(14 * 60 + 15, 14 * 60 + 45, "PE", "SCALP PE"), tape, 10 * 60, true);
    expect(g.kind).toBe("PENDING");
  });

  it("parses a yahoo chart payload", () => {
    const t9 = Math.floor(utcFromIstParts(2026, 8, 26, 9, 15, 0).getTime() / 1000);
    const parsed = parseYahooChart(
      {
        chart: {
          result: [
            {
              meta: { chartPreviousClose: 24334.55 },
              timestamp: [t9],
              indicators: { quote: [{ open: [24341], high: [24355], low: [24310], close: [24318] }] },
            },
          ],
        },
      },
      "2026-08-26",
      "NIFTY",
    );
    expect(parsed.bars.length).toBe(1);
    expect(parsed.prevClose).toBe(24334.55);
    expect(parsed.sessionOpen).toBe(24341);
  });

  it("summarises hit-rate without counting sits", () => {
    const slots = [
      { fromMin: 555, toMin: 585, side: "WAIT", action: "WAIT" },
      { fromMin: 585, toMin: 615, side: "PE", action: "SCALP PE" },
    ] as WindowSlot[];
    const sum = summariseTape(slots, tape, 16 * 60, false, "flat");
    expect(sum.sits).toBe(1);
    expect(sum.directional).toBe(1);
    expect(sum.hits).toBe(1);
    expect(sum.gapActual).toBe("flat");
    expect(sum.gapHit).toBe(true);
  });

  it("names the Nifty buy strike from window-open spot", () => {
    expect(roundStrike(24763, 50)).toBe(24750);
    const pe = buyContract(
      { fromMin: 555, toMin: 585, side: "PE", action: "SCALP PE", product: "NIFTY ATM PE" },
      tape,
    );
    expect(pe.verb).toBe("BUY");
    expect(pe.strike).toBe(24350);
    expect(pe.short).toBe("24,350 PE");
    expect(pe.label).toBe("BUY 24,350 PE");

    const otm = buyContract(
      { fromMin: 555, toMin: 585, side: "PE", action: "SCALP PE", product: "NIFTY 100 pts OTM PE" },
      tape,
    );
    expect(otm.strike).toBe(24350);

    const ce = buyContract(
      { fromMin: 555, toMin: 585, side: "CE", action: "BUY CE", product: "NIFTY 50 pts OTM CE" },
      tape,
    );
    expect(ce.strike).toBe(24350);
    expect(ce.label).toBe("BUY 24,350 CE");

    const sit = buyContract(
      { fromMin: 555, toMin: 585, side: "WAIT", action: "WAIT", product: "No contract" },
      tape,
    );
    expect(sit.verb).toBe("SIT");
    expect(sit.label).toBe("—");

    const book = buyContract(
      { fromMin: 555, toMin: 585, side: "PE", action: "BOOK PE", product: "NIFTY ATM PE" },
      tape,
    );
    expect(book.verb).toBe("BOOK");
    expect(book.label.startsWith("BOOK ")).toBe(true);
  });
});
