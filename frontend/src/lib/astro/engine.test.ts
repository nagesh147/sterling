/* Runs under vitest like every other test here. It arrived importing
   `node:test` and `node:assert/strict`, which this project has no types for and
   the vitest runner cannot collect — so the file failed to load and the whole
   suite was red. Same assertions, vitest's API. */
import { describe, it, expect } from "vitest";
import { forecastDay, forecastMonth, liveNow } from "./engine";
import { lastCompletedSessionIso, nearestOpenIso, nextSessionIso, shiftSessionIso } from "./holidays";
import { utcFromIstParts } from "./time";

/* Thin shims so the 90 existing assertions keep their original shape — this is a
   mechanical conversion, not a rewrite of someone else's test. */
const expectIs = (actual: unknown, expected: unknown, msg?: string) =>
  expect(actual, msg as string).toBe(expected);
const expectNot = (actual: unknown, expected: unknown, msg?: string) =>
  expect(actual, msg as string).not.toBe(expected);
const expectDeep = (actual: unknown, expected: unknown, msg?: string) =>
  expect(actual, msg as string).toEqual(expected);
/* An assertion function, not a plain call: `assert.ok` narrowed the type for
   everything after it, and a `find()` result is `T | undefined`. Without the
   `asserts` signature every later use of that value stops compiling, and
   sprinkling `!` through someone else's test to paper over it would be losing
   the check rather than converting it. */
function expectOk(value: unknown, msg?: string): asserts value {
  expect(value, msg as string).toBeTruthy();
}


describe("financial astrology engine", () => {
  const session = utcFromIstParts(2026, 8, 26, 9, 0, 0);

  it("is deterministic for a given IST date", () => {
    const a = forecastDay(session, "NIFTY", session);
    const b = forecastDay(session, "NIFTY", session);
    expectIs(a.gap.kind, b.gap.kind);
    expectIs(a.gap.label, b.gap.label);
    expectIs(a.slots.length, b.slots.length);
    expectDeep(
      a.slots.map((s) => s.regime),
      b.slots.map((s) => s.regime),
    );
    expectDeep(
      a.slots.map((s) => s.action),
      b.slots.map((s) => s.action),
    );
  });

  it("prints a full cash-session 30-minute clock", () => {
    const book = forecastDay(session, "BANKNIFTY", session);
    expectIs(book.slots.length, 13);
    expectIs(book.slots[0].from, "9:15 AM");
    expectIs(book.slots[book.slots.length - 1].to, "3:30 PM");
    expectOk(book.netResults.length >= 8);
    expectOk(book.netResults.length <= 18);
    expectIs(book.netResults[0].from, "9:15 AM");
    expectIs(book.netResults[book.netResults.length - 1].to, "3:30 PM");
    const grid = new Set([555, 585, 615, 645, 675, 705, 735, 765, 795, 825, 855, 885, 915]);
    const offGrid = book.netResults.filter((s) => !grid.has(s.fromMin) && s.fromMin !== 555);
    expectOk(offGrid.length >= 3, "astro timings must cut inside the 30-min grid");
  });

  it("always suggests CE, PE, both, or wait in trading language", () => {
    const book = forecastDay(session, "NIFTY", session);
    for (const slot of book.slots) {
      expectOk(["CE", "PE", "BOTH", "WAIT"].includes(slot.side));
      expectOk(slot.action.length > 0);
      expectOk(slot.suggestion.length > 10);
      expectOk(slot.choghadiya.length > 0);
      expectOk(["good", "move", "bad"].includes(slot.choghadiyaKind));
      expectOk(slot.product.length > 0);
      expectOk(slot.hora.length > 0);
      expectOk(slot.lagna.length > 0);
    }
    expectOk(["up", "flat", "down"].includes(book.gap.kind));
    expectOk(book.gap.confidence >= 50 && book.gap.confidence <= 94);
    expectOk(book.gap.horaAtOpen);
    expectOk(Array.isArray(book.gap.yogas));
    expectOk(book.aspects.length >= 0);
    expectIs(book.dignities.length, 9);
  });

  it("projects only NSE trading days in a month", () => {
    const month = forecastMonth(2026, 8, "NIFTY", session);
    expectIs(month.month, 8);
    expectOk(month.tradingDays >= 18 && month.tradingDays <= 23);
    expectIs(month.gapUp + month.gapDown + month.gapFlat, month.tradingDays);
    const fifteenth = month.days.find((d) => d.date === "2026-08-15");
    expectOk(fifteenth);
    expectIs(fifteenth.isWeekend, true);
  });

  it("uses today's Mumbai sunrise so hora actually changes in cash hours", () => {
    const book = forecastDay(session, "NIFTY", session);
    const rise = new Date(book.panchang.sunriseIso);
    const set = new Date(book.panchang.sunsetIso);
    const riseIst = new Date(rise.getTime() + 5.5 * 3600 * 1000);
    const setIst = new Date(set.getTime() + 5.5 * 3600 * 1000);
    expectIs(riseIst.getUTCDate(), 26);
    expectIs(riseIst.getUTCMonth() + 1, 8);
    expectOk(riseIst.getUTCHours() >= 5 && riseIst.getUTCHours() <= 7);
    expectOk(setIst.getUTCHours() >= 18 && setIst.getUTCHours() <= 20);
    const horas = new Set(book.slots.map((s) => s.hora));
    expectOk(horas.size >= 3, `expected multiple horas, got ${[...horas].join(",")}`);
    expectOk(book.gap.horaAtOpen);
    expectNot(book.slots[0].hora, book.slots[book.slots.length - 1].hora);
  });

  it("sits the bell on a Rikta + nodal-affliction fade day, and hora does not flip the residual", () => {
    const nifty = forecastDay(session, "NIFTY", session);
    expectIs(nifty.gap.thesis, "fade");
    expectIs(nifty.gap.openAction, "WAIT");
    expectIs(nifty.slots[0].action, "WAIT");
    expectNot(nifty.gap.volatility, "extreme");
    const directional = nifty.slots.filter((s) => s.side === "CE" || s.side === "PE");
    const pe = directional.filter((s) => s.side === "PE").length;
    expectOk(pe >= directional.length - 1, `fade residual should stay PE, got ${directional.map((s) => s.action).join(",")}`);
    expectOk(nifty.playbook.closeBias.includes("Negative") || nifty.playbook.closeBias.includes("Sideways"));
  });

  it("Yamagandam never issues a fresh BUY", () => {
    const book = forecastDay(session, "NIFTY", session);
    for (const s of book.slots) {
      if (s.kalam.yamagandam) {
        expectOk(s.action === "WAIT" || s.action === "AVOID", `${s.from} Yamagandam issued ${s.action}`);
      }
    }
  });

  it("Bank Nifty can disagree with Nifty on the same sky — sector lords", () => {
    const nifty = forecastDay(session, "NIFTY", session);
    const bank = forecastDay(session, "BANKNIFTY", session);
    expectIs(nifty.gap.thesis, "fade");
    expectIs(bank.gap.thesis, "fade");
    expectIs(bank.slots[0].action, "WAIT");
    const nSides = nifty.slots.filter((s) => s.side === "CE" || s.side === "PE").map((s) => s.side);
    const bSides = bank.slots.filter((s) => s.side === "CE" || s.side === "PE").map((s) => s.side);
    expectOk(nSides.length + bSides.length > 0);
    const nPe = nSides.filter((s) => s === "PE").length;
    const bCe = bSides.filter((s) => s === "CE").length;
    expectOk(nPe > nSides.length / 2, `Nifty residual should be PE, got ${nSides.join(",")}`);
    expectOk(bCe > bSides.length / 2, `Bank residual should be CE, got ${bSides.join(",")}`);
  });

  it("astro timings pin the 30-min opening range, then cut on muhurta", () => {
    const book = forecastDay(session, "NIFTY", session);
    expectIs(book.netResults[0].from, "9:15 AM");
    expectIs(book.netResults[0].to, "9:45 AM");
    expectIs(book.netResults[0].action, "WAIT");
    const yama = book.netResults.filter((s) => s.kalam.yamagandam);
    for (const s of yama) {
      expectOk(s.action === "WAIT" || s.action === "AVOID", `${s.from}–${s.to} Yamagandam issued ${s.action}`);
    }
    const lens = book.netResults.slice(1).map((s) => s.toMin - s.fromMin);
    expectOk(lens.some((n) => n !== 30), `expected irregular muhurta lengths, got ${lens.join(",")}`);
    const grid = new Set([555, 585, 615, 645, 675, 705, 735, 765, 795, 825, 855, 885, 915]);
    const offGrid = book.netResults.filter((s) => !grid.has(s.fromMin));
    expectOk(offGrid.length >= 3, "astro timings must cut inside the 30-min grid after the open");
  });

  it("grades last cash session before the bell, not the empty next day", () => {
    expectIs(lastCompletedSessionIso(utcFromIstParts(2026, 8, 27, 0, 18, 0)), "2026-08-26");
    expectIs(lastCompletedSessionIso(utcFromIstParts(2026, 8, 26, 10, 0, 0)), "2026-08-26");
    expectIs(lastCompletedSessionIso(utcFromIstParts(2026, 8, 26, 16, 0, 0)), "2026-08-26");
    expectIs(lastCompletedSessionIso(utcFromIstParts(2026, 8, 23, 11, 0, 0)), "2026-08-21");
  });

  it("points the live now board at the next cash session, not last night's tape", () => {
    expectIs(nextSessionIso(utcFromIstParts(2026, 8, 27, 0, 18, 0)), "2026-08-27");
    expectIs(nextSessionIso(utcFromIstParts(2026, 8, 26, 10, 0, 0)), "2026-08-26");
    expectIs(nextSessionIso(utcFromIstParts(2026, 8, 26, 16, 0, 0)), "2026-08-27");
    expectIs(nextSessionIso(utcFromIstParts(2026, 8, 29, 11, 0, 0)), "2026-08-31");
    expectIs(shiftSessionIso("2026-08-26", 1), "2026-08-27");
    expectIs(shiftSessionIso("2026-08-28", 1), "2026-08-31");
    expectIs(shiftSessionIso("2026-08-31", -1), "2026-08-28");
    expectIs(nearestOpenIso("2026-08-26"), "2026-08-26");
    expectIs(nearestOpenIso("2026-08-30"), "2026-08-28");

    const pre = liveNow(utcFromIstParts(2026, 8, 27, 0, 18, 0), "NIFTY");
    expectIs(pre.phase, "pre");
    expectIs(pre.sessionIso, "2026-08-27");
    expectIs(pre.window, null);
    expectOk(pre.next);
    expectIs(pre.next?.from, "9:15 AM");
    expectIs(pre.play, pre.gap.openAction);
    expectOk(pre.hora.index >= 12, "00:18 IST is a night hora");
    expectIs(pre.choghadiya, "Night");
    expectIs(pre.kalam.rahu, false);

    const live = liveNow(utcFromIstParts(2026, 8, 26, 10, 22, 0), "NIFTY");
    expectIs(live.phase, "live");
    expectOk(live.window);
    expectIs(live.window?.isLive, true);
    expectOk(live.window && live.window.fromMin <= 622 && live.window.toMin > 622);
    expectOk(live.hora.index < 12);

    const post = liveNow(utcFromIstParts(2026, 8, 26, 16, 5, 0), "NIFTY");
    expectIs(post.phase, "post");
    expectIs(post.sessionIso, "2026-08-27");
    expectIs(post.window, null);

    const closed = liveNow(utcFromIstParts(2026, 8, 29, 11, 0, 0), "NIFTY");
    expectIs(closed.phase, "closed");
    expectIs(closed.sessionIso, "2026-08-31");
  });
});
