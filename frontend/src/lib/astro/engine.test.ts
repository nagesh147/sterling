import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { forecastDay, forecastMonth, liveNow } from "./engine";
import { lastCompletedSessionIso, nextSessionIso } from "./holidays";
import { utcFromIstParts } from "./time";

describe("financial astrology engine", () => {
  const session = utcFromIstParts(2026, 8, 26, 9, 0, 0);

  it("is deterministic for a given IST date", () => {
    const a = forecastDay(session, "NIFTY", session);
    const b = forecastDay(session, "NIFTY", session);
    assert.equal(a.gap.kind, b.gap.kind);
    assert.equal(a.gap.label, b.gap.label);
    assert.equal(a.slots.length, b.slots.length);
    assert.deepEqual(
      a.slots.map((s) => s.regime),
      b.slots.map((s) => s.regime),
    );
    assert.deepEqual(
      a.slots.map((s) => s.action),
      b.slots.map((s) => s.action),
    );
  });

  it("prints a full cash-session 30-minute clock", () => {
    const book = forecastDay(session, "BANKNIFTY", session);
    assert.equal(book.slots.length, 13);
    assert.equal(book.slots[0].from, "9:15 AM");
    assert.equal(book.slots[book.slots.length - 1].to, "3:30 PM");
    assert.ok(book.netResults.length >= 8);
    assert.ok(book.netResults.length <= 18);
    assert.equal(book.netResults[0].from, "9:15 AM");
    assert.equal(book.netResults[book.netResults.length - 1].to, "3:30 PM");
    const grid = new Set([555, 585, 615, 645, 675, 705, 735, 765, 795, 825, 855, 885, 915]);
    const offGrid = book.netResults.filter((s) => !grid.has(s.fromMin) && s.fromMin !== 555);
    assert.ok(offGrid.length >= 3, "astro timings must cut inside the 30-min grid");
  });

  it("always suggests CE, PE, both, or wait in trading language", () => {
    const book = forecastDay(session, "NIFTY", session);
    for (const slot of book.slots) {
      assert.ok(["CE", "PE", "BOTH", "WAIT"].includes(slot.side));
      assert.ok(slot.action.length > 0);
      assert.ok(slot.suggestion.length > 10);
      assert.ok(slot.choghadiya.length > 0);
      assert.ok(["good", "move", "bad"].includes(slot.choghadiyaKind));
      assert.ok(slot.product.length > 0);
      assert.ok(slot.hora.length > 0);
      assert.ok(slot.lagna.length > 0);
    }
    assert.ok(["up", "flat", "down"].includes(book.gap.kind));
    assert.ok(book.gap.confidence >= 50 && book.gap.confidence <= 94);
    assert.ok(book.gap.horaAtOpen);
    assert.ok(Array.isArray(book.gap.yogas));
    assert.ok(book.aspects.length >= 0);
    assert.equal(book.dignities.length, 9);
  });

  it("projects only NSE trading days in a month", () => {
    const month = forecastMonth(2026, 8, "NIFTY", session);
    assert.equal(month.month, 8);
    assert.ok(month.tradingDays >= 18 && month.tradingDays <= 23);
    assert.equal(month.gapUp + month.gapDown + month.gapFlat, month.tradingDays);
    const fifteenth = month.days.find((d) => d.date === "2026-08-15");
    assert.ok(fifteenth);
    assert.equal(fifteenth.isWeekend, true);
  });

  it("uses today's Mumbai sunrise so hora actually changes in cash hours", () => {
    const book = forecastDay(session, "NIFTY", session);
    const rise = new Date(book.panchang.sunriseIso);
    const set = new Date(book.panchang.sunsetIso);
    const riseIst = new Date(rise.getTime() + 5.5 * 3600 * 1000);
    const setIst = new Date(set.getTime() + 5.5 * 3600 * 1000);
    assert.equal(riseIst.getUTCDate(), 26);
    assert.equal(riseIst.getUTCMonth() + 1, 8);
    assert.ok(riseIst.getUTCHours() >= 5 && riseIst.getUTCHours() <= 7);
    assert.ok(setIst.getUTCHours() >= 18 && setIst.getUTCHours() <= 20);
    const horas = new Set(book.slots.map((s) => s.hora));
    assert.ok(horas.size >= 3, `expected multiple horas, got ${[...horas].join(",")}`);
    assert.ok(book.gap.horaAtOpen);
    assert.notEqual(book.slots[0].hora, book.slots[book.slots.length - 1].hora);
  });

  it("sits the bell on a Rikta + nodal-affliction fade day, and hora does not flip the residual", () => {
    const nifty = forecastDay(session, "NIFTY", session);
    assert.equal(nifty.gap.thesis, "fade");
    assert.equal(nifty.gap.openAction, "WAIT");
    assert.equal(nifty.slots[0].action, "WAIT");
    assert.notEqual(nifty.gap.volatility, "extreme");
    const directional = nifty.slots.filter((s) => s.side === "CE" || s.side === "PE");
    const pe = directional.filter((s) => s.side === "PE").length;
    assert.ok(pe >= directional.length - 1, `fade residual should stay PE, got ${directional.map((s) => s.action).join(",")}`);
    assert.ok(nifty.playbook.closeBias.includes("Negative") || nifty.playbook.closeBias.includes("Sideways"));
  });

  it("Yamagandam never issues a fresh BUY", () => {
    const book = forecastDay(session, "NIFTY", session);
    for (const s of book.slots) {
      if (s.kalam.yamagandam) {
        assert.ok(s.action === "WAIT" || s.action === "AVOID", `${s.from} Yamagandam issued ${s.action}`);
      }
    }
  });

  it("Bank Nifty can disagree with Nifty on the same sky — sector lords", () => {
    const nifty = forecastDay(session, "NIFTY", session);
    const bank = forecastDay(session, "BANKNIFTY", session);
    assert.equal(nifty.gap.thesis, "fade");
    assert.equal(bank.gap.thesis, "fade");
    assert.equal(bank.slots[0].action, "WAIT");
    const nSides = nifty.slots.filter((s) => s.side === "CE" || s.side === "PE").map((s) => s.side);
    const bSides = bank.slots.filter((s) => s.side === "CE" || s.side === "PE").map((s) => s.side);
    assert.ok(nSides.length + bSides.length > 0);
    const nPe = nSides.filter((s) => s === "PE").length;
    const bCe = bSides.filter((s) => s === "CE").length;
    assert.ok(nPe > nSides.length / 2, `Nifty residual should be PE, got ${nSides.join(",")}`);
    assert.ok(bCe > bSides.length / 2, `Bank residual should be CE, got ${bSides.join(",")}`);
  });

  it("astro timings pin the 30-min opening range, then cut on muhurta", () => {
    const book = forecastDay(session, "NIFTY", session);
    assert.equal(book.netResults[0].from, "9:15 AM");
    assert.equal(book.netResults[0].to, "9:45 AM");
    assert.equal(book.netResults[0].action, "WAIT");
    const yama = book.netResults.filter((s) => s.kalam.yamagandam);
    for (const s of yama) {
      assert.ok(s.action === "WAIT" || s.action === "AVOID", `${s.from}–${s.to} Yamagandam issued ${s.action}`);
    }
    const lens = book.netResults.slice(1).map((s) => s.toMin - s.fromMin);
    assert.ok(lens.some((n) => n !== 30), `expected irregular muhurta lengths, got ${lens.join(",")}`);
    const grid = new Set([555, 585, 615, 645, 675, 705, 735, 765, 795, 825, 855, 885, 915]);
    const offGrid = book.netResults.filter((s) => !grid.has(s.fromMin));
    assert.ok(offGrid.length >= 3, "astro timings must cut inside the 30-min grid after the open");
  });

  it("grades last cash session before the bell, not the empty next day", () => {
    assert.equal(lastCompletedSessionIso(utcFromIstParts(2026, 8, 27, 0, 18, 0)), "2026-08-26");
    assert.equal(lastCompletedSessionIso(utcFromIstParts(2026, 8, 26, 10, 0, 0)), "2026-08-26");
    assert.equal(lastCompletedSessionIso(utcFromIstParts(2026, 8, 26, 16, 0, 0)), "2026-08-26");
    assert.equal(lastCompletedSessionIso(utcFromIstParts(2026, 8, 23, 11, 0, 0)), "2026-08-21");
  });

  it("points the live now board at the next cash session, not last night's tape", () => {
    assert.equal(nextSessionIso(utcFromIstParts(2026, 8, 27, 0, 18, 0)), "2026-08-27");
    assert.equal(nextSessionIso(utcFromIstParts(2026, 8, 26, 10, 0, 0)), "2026-08-26");
    assert.equal(nextSessionIso(utcFromIstParts(2026, 8, 26, 16, 0, 0)), "2026-08-27");
    assert.equal(nextSessionIso(utcFromIstParts(2026, 8, 29, 11, 0, 0)), "2026-08-31");

    const pre = liveNow(utcFromIstParts(2026, 8, 27, 0, 18, 0), "NIFTY");
    assert.equal(pre.phase, "pre");
    assert.equal(pre.sessionIso, "2026-08-27");
    assert.equal(pre.window, null);
    assert.ok(pre.next);
    assert.equal(pre.next?.from, "9:15 AM");
    assert.equal(pre.play, pre.gap.openAction);
    assert.ok(pre.hora.index >= 12, "00:18 IST is a night hora");
    assert.equal(pre.choghadiya, "Night");
    assert.equal(pre.kalam.rahu, false);

    const live = liveNow(utcFromIstParts(2026, 8, 26, 10, 22, 0), "NIFTY");
    assert.equal(live.phase, "live");
    assert.ok(live.window);
    assert.equal(live.window?.isLive, true);
    assert.ok(live.window && live.window.fromMin <= 622 && live.window.toMin > 622);
    assert.ok(live.hora.index < 12);

    const post = liveNow(utcFromIstParts(2026, 8, 26, 16, 5, 0), "NIFTY");
    assert.equal(post.phase, "post");
    assert.equal(post.sessionIso, "2026-08-27");
    assert.equal(post.window, null);

    const closed = liveNow(utcFromIstParts(2026, 8, 29, 11, 0, 0), "NIFTY");
    assert.equal(closed.phase, "closed");
    assert.equal(closed.sessionIso, "2026-08-31");
  });
});
