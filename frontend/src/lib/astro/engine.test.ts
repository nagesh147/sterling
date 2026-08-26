import { describe, it, expect } from "vitest";
import { forecastDay, forecastMonth } from "./engine";
import { lastCompletedSessionIso } from "./holidays";
import { utcFromIstParts } from "./time";

describe("financial astrology engine", () => {
  const session = utcFromIstParts(2026, 8, 26, 9, 0, 0);

  it("is deterministic for a given IST date", () => {
    const a = forecastDay(session, "NIFTY", session);
    const b = forecastDay(session, "NIFTY", session);
    expect(a.gap.kind).toBe(b.gap.kind);
    expect(a.gap.label).toBe(b.gap.label);
    expect(a.slots.length).toBe(b.slots.length);
    expect(a.slots.map((s) => s.regime)).toEqual(b.slots.map((s) => s.regime));
    expect(a.slots.map((s) => s.action)).toEqual(b.slots.map((s) => s.action));
  });

  it("prints a full cash-session 30-minute clock", () => {
    const book = forecastDay(session, "BANKNIFTY", session);
    expect(book.slots.length).toBe(13);
    expect(book.slots[0].from).toBe("9:15 AM");
    expect(book.slots[book.slots.length - 1].to).toBe("3:30 PM");
    expect(book.netResults.length).toBeGreaterThanOrEqual(8);
    expect(book.netResults.length).toBeLessThanOrEqual(18);
    expect(book.netResults[0].from).toBe("9:15 AM");
    expect(book.netResults[book.netResults.length - 1].to).toBe("3:30 PM");
  });

  it("always suggests CE, PE, both, or wait in trading language", () => {
    const book = forecastDay(session, "NIFTY", session);
    for (const slot of book.slots) {
      expect(["CE", "PE", "BOTH", "WAIT"]).toContain(slot.side);
      expect(slot.action.length).toBeGreaterThan(0);
      expect(slot.suggestion.length).toBeGreaterThan(10);
      expect(slot.choghadiya.length).toBeGreaterThan(0);
      expect(["good", "move", "bad"]).toContain(slot.choghadiyaKind);
    }
    expect(["up", "flat", "down"]).toContain(book.gap.kind);
    expect(book.gap.confidence).toBeGreaterThanOrEqual(50);
    expect(book.gap.confidence).toBeLessThanOrEqual(94);
    expect(book.gap.horaAtOpen).toBeTruthy();
    expect(book.dignities.length).toBe(9);
  });

  it("projects only NSE trading days in a month", () => {
    const month = forecastMonth(2026, 8, "NIFTY", session);
    expect(month.month).toBe(8);
    expect(month.tradingDays).toBeGreaterThanOrEqual(18);
    expect(month.tradingDays).toBeLessThanOrEqual(23);
    expect(month.gapUp + month.gapDown + month.gapFlat).toBe(month.tradingDays);
    const fifteenth = month.days.find((d) => d.date === "2026-08-15");
    expect(fifteenth).toBeTruthy();
    expect(fifteenth?.isWeekend).toBe(true);
  });

  it("uses today's Mumbai sunrise so hora actually changes in cash hours", () => {
    const book = forecastDay(session, "NIFTY", session);
    const rise = new Date(book.panchang.sunriseIso);
    const set = new Date(book.panchang.sunsetIso);
    const riseIst = new Date(rise.getTime() + 5.5 * 3600 * 1000);
    const setIst = new Date(set.getTime() + 5.5 * 3600 * 1000);
    expect(riseIst.getUTCDate()).toBe(26);
    expect(riseIst.getUTCMonth() + 1).toBe(8);
    expect(riseIst.getUTCHours()).toBeGreaterThanOrEqual(5);
    expect(riseIst.getUTCHours()).toBeLessThanOrEqual(7);
    expect(setIst.getUTCHours()).toBeGreaterThanOrEqual(18);
    expect(setIst.getUTCHours()).toBeLessThanOrEqual(20);
    const horas = new Set(book.slots.map((s) => s.hora));
    expect(horas.size).toBeGreaterThanOrEqual(3);
    expect(book.gap.horaAtOpen).toBeTruthy();
    expect(book.slots[0].hora).not.toBe(book.slots[book.slots.length - 1].hora);
  });

  it("sits the bell on a Rikta + nodal-affliction fade day, and hora does not flip the residual", () => {
    const nifty = forecastDay(session, "NIFTY", session);
    expect(nifty.gap.thesis).toBe("fade");
    expect(nifty.gap.openAction).toBe("WAIT");
    expect(nifty.slots[0].action).toBe("WAIT");
    expect(nifty.gap.volatility).not.toBe("extreme");
    const directional = nifty.slots.filter((s) => s.side === "CE" || s.side === "PE");
    const pe = directional.filter((s) => s.side === "PE").length;
    expect(pe).toBeGreaterThanOrEqual(directional.length - 1);
  });

  it("Yamagandam never issues a fresh BUY", () => {
    const book = forecastDay(session, "NIFTY", session);
    for (const s of book.slots) {
      if (s.kalam.yamagandam) {
        expect(["WAIT", "AVOID"]).toContain(s.action);
      }
    }
  });

  it("Bank Nifty can disagree with Nifty on the same sky — sector lords", () => {
    const nifty = forecastDay(session, "NIFTY", session);
    const bank = forecastDay(session, "BANKNIFTY", session);
    expect(nifty.gap.thesis).toBe("fade");
    expect(bank.gap.thesis).toBe("fade");
    expect(bank.slots[0].action).toBe("WAIT");
    const nSides = nifty.slots.filter((s) => s.side === "CE" || s.side === "PE").map((s) => s.side);
    const bSides = bank.slots.filter((s) => s.side === "CE" || s.side === "PE").map((s) => s.side);
    const nPe = nSides.filter((s) => s === "PE").length;
    const bCe = bSides.filter((s) => s === "CE").length;
    expect(nPe).toBeGreaterThan(nSides.length / 2);
    expect(bCe).toBeGreaterThan(bSides.length / 2);
  });

  it("astro timings pin the 30-min opening range, then cut on muhurta", () => {
    const book = forecastDay(session, "NIFTY", session);
    expect(book.netResults[0].from).toBe("9:15 AM");
    expect(book.netResults[0].to).toBe("9:45 AM");
    expect(book.netResults[0].action).toBe("WAIT");
    const lens = book.netResults.slice(1).map((s) => s.toMin - s.fromMin);
    expect(lens.some((n) => n !== 30)).toBe(true);
    const grid = new Set([555, 585, 615, 645, 675, 705, 735, 765, 795, 825, 855, 885, 915]);
    const offGrid = book.netResults.filter((s) => !grid.has(s.fromMin));
    expect(offGrid.length).toBeGreaterThanOrEqual(3);
  });

  it("grades last cash session before the bell, not the empty next day", () => {
    expect(lastCompletedSessionIso(utcFromIstParts(2026, 8, 27, 0, 18, 0))).toBe("2026-08-26");
    expect(lastCompletedSessionIso(utcFromIstParts(2026, 8, 26, 10, 0, 0))).toBe("2026-08-26");
    expect(lastCompletedSessionIso(utcFromIstParts(2026, 8, 26, 16, 0, 0))).toBe("2026-08-26");
    expect(lastCompletedSessionIso(utcFromIstParts(2026, 8, 23, 11, 0, 0))).toBe("2026-08-21");
  });
});
