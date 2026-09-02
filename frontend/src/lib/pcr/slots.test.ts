import { describe, it, expect } from "vitest";
import {
  SLOT_HHMM,
  SHOT_2026_08_27,
  bandTitle,
  buildGrid,
  compareShot,
  describeFlow,
  formatPcr,
  hhmmToMinutes,
  isValidPrint,
  overlayShot,
  pcrBand,
  putShare,
  readPcr,
  roundPcr,
  formatDeskStamp,
  slotLabel,
} from "./slots";
import { PCR_SNAPSHOT, snapshotSeries } from "./snapshot";
import { PCR_INDICES } from "./types";

describe("pcr slots", () => {
  it("prints a 15-min cash clock from 9.15 to 15.30", () => {
    expect(SLOT_HHMM.length).toBe(26);
    expect(SLOT_HHMM[0]).toBe("09:15");
    expect(SLOT_HHMM[SLOT_HHMM.length - 1]).toBe("15:30");
    expect(slotLabel("09:15")).toBe("9.15");
    expect(slotLabel("15:30")).toBe("15.30");
  });

  it("colours the screenshot legend bands", () => {
    expect(pcrBand(1.4)).toBe("extreme-positive");
    expect(pcrBand(1.2)).toBe("highly-positive");
    expect(pcrBand(1)).toBe("positive");
    expect(pcrBand(0.99)).toBe("negative");
    expect(pcrBand(0.8)).toBe("highly-negative");
    expect(pcrBand(0.7)).toBe("highly-negative");
    expect(pcrBand(0.6)).toBe("extreme-negative");
    expect(pcrBand(0.56)).toBe("extreme-negative");
    expect(bandTitle("extreme-negative")).toBe("Extreme Negative");
  });

  it("rounds to two decimals the way the print does", () => {
    expect(roundPcr(0.7005)).toBe(0.7);
    expect(formatPcr(0.7005)).toBe("0.70");
    expect(formatPcr(0.5575)).toBe("0.56");
    expect(formatPcr(0.5939)).toBe("0.59");
  });

  it("fills 15.15 as live at 15:14 and leaves 15.30 blank", () => {
    const nifty = PCR_SNAPSHOT.NIFTY;
    const grid = buildGrid(nifty.marks, { hhmm: "15:14", pcr: 0.5939, volumePcr: 1.04, changeOiPcr: 0.28, indexClose: 24133 }, 15 * 60 + 14);
    const s1515 = grid.find((s) => s.hhmm === "15:15");
    const s1530 = grid.find((s) => s.hhmm === "15:30");
    const s1500 = grid.find((s) => s.hhmm === "15:00");
    expect(s1515?.live).toBe(true);
    expect(roundPcr(s1515?.pcr ?? 0)).toBe(0.59);
    expect(s1530?.pcr).toBe(null);
    expect(s1500?.live).toBe(false);
    expect(roundPcr(s1500?.pcr ?? 0)).toBe(0.6);
  });

  it("paints the full session after cash close and before the next open", () => {
    const series = snapshotSeries("NIFTY");
    const after = buildGrid(series.marks, series.latest, 16 * 60);
    const pre = buildGrid(series.marks, series.latest, 8 * 60 + 10);
    expect(after.filter((s) => s.pcr != null).length).toBe(26);
    expect(pre.filter((s) => s.pcr != null).length).toBe(26);
    expect(after.find((s) => s.hhmm === "15:30")?.live).toBe(false);
  });

  it("matches the 27 Aug Nifty print on 25 of 25 published cells", () => {
    const series = snapshotSeries("NIFTY");
    const grid = buildGrid(series.marks, series.latest, 15 * 60 + 30);
    const cmp = compareShot(grid);
    expect(cmp.total).toBe(25);
    expect(cmp.matched, `only ${cmp.matched}/25 matched: ${JSON.stringify(cmp.diffs)}`).toBe(25);
  });

  it("matches every index on the 27 Aug Intraday + Weekly print", () => {
    for (const row of PCR_INDICES) {
      const series = snapshotSeries(row.id);
      const grid = buildGrid(series.marks, series.latest, 15 * 60 + 30);
      const cmp = compareShot(grid, SHOT_2026_08_27[row.id]);
      expect(cmp.total, row.id).toBe(26);
      expect(cmp.matched, `${row.id} ${cmp.matched}/26 ${JSON.stringify(cmp.diffs)}`).toBe(26);
    }
  });

  it("overlays shot PCR without dropping marks", () => {
    const raw = PCR_SNAPSHOT.NIFTY.marks;
    const over = overlayShot(raw, SHOT_2026_08_27.NIFTY);
    expect(over.length).toBe(raw.length);
    expect(roundPcr(over[0]?.pcr ?? 0)).toBe(0.7);
    expect(raw[0]?.pcr).toBe(0.7332);
  });

  it("keeps put share in (0,1) from PCR", () => {
    expect(Number(putShare(1)?.toFixed(2))).toBe(0.5);
    expect(putShare(0.59) ?? 0).toBeLessThan(0.4);
  });

  it("reads put writing vs protective buying from PCR vs spot", () => {
    expect(readPcr([], null).headline).toBe("Waiting for the open print");
    expect(readPcr([], null).action).toBe("Stand aside");
    const rising = [
      { hhmm: "09:15", label: "9.15", minutes: 555, pcr: 0.80, delta: null, band: "highly-negative" as const, live: false },
      { hhmm: "09:30", label: "9.30", minutes: 570, pcr: 0.90, delta: 0.10, band: "negative" as const, live: false },
      { hhmm: "09:45", label: "9.45", minutes: 585, pcr: 0.98, delta: 0.08, band: "negative" as const, live: true },
    ];
    expect(readPcr(rising, -0.4)).toMatchObject({ bias: "Bearish", headline: "Puts being bought into weakness", action: "Buy PE" });
    expect(readPcr(rising, 0.3)).toMatchObject({ bias: "Bullish", headline: "Put writing on the bounce", action: "Buy CE" });
    const falling = [
      { hhmm: "09:15", label: "9.15", minutes: 555, pcr: 1.05, delta: null, band: "positive" as const, live: false },
      { hhmm: "09:30", label: "9.30", minutes: 570, pcr: 0.95, delta: -0.10, band: "negative" as const, live: true },
    ];
    expect(readPcr(falling, 0.5).headline).toBe("Calls chasing the rally");
    expect(readPcr(
      [{ hhmm: "09:15", label: "9.15", minutes: 555, pcr: 1.35, delta: null, band: "highly-positive" as const, live: true }],
      0,
    )).toMatchObject({ headline: "Put writers in control", action: "Buy CE" });
    expect(readPcr(
      [{ hhmm: "09:15", label: "9.15", minutes: 555, pcr: 0.62, delta: null, band: "highly-negative" as const, live: true }],
      0,
    )).toMatchObject({ headline: "Call load is heavy", action: "Buy PE" });
    expect(readPcr(
      [{ hhmm: "09:15", label: "9.15", minutes: 555, pcr: 0.95, delta: null, band: "negative" as const, live: true }],
      0,
    ).action).toBe("Stand aside");
  });

  it("formats the desk stamp as 02 Sept 2026 09:15 AM", () => {
    expect(formatDeskStamp("2026-09-02", "09:15")).toBe("02 Sept 2026 09:15 AM");
    expect(formatDeskStamp("2026-09-02", "15:30")).toBe("02 Sept 2026 03:30 PM");
    expect(isValidPrint(0)).toBe(false);
    expect(isValidPrint(0.74)).toBe(true);
    expect(isValidPrint(-2.32)).toBe(false);
  });

  it("says Buy CE or Buy PE in plain language on the flow tape", () => {
    const ce = describeFlow("Midcap", "14:45", 1.21, 0.11);
    expect(ce.action).toBe("Buy CE");
    expect(ce.detail).toMatch(/rose/i);
    expect(ce.detail).not.toMatch(/thickening|taking share/i);
    const pe = describeFlow("Midcap", "15:15", 1.12, -0.08);
    expect(pe.action).toBe("Buy PE");
    expect(pe.title).toMatch(/Buy PE/);
    expect(pe.detail).toMatch(/fell/i);
  });

  it("has a mark for every cash slot on the snapshot", () => {
    for (const id of ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "MIDCPNIFTY"] as const) {
      expect(PCR_SNAPSHOT[id].marks.length, id).toBe(26);
    }
    expect(hhmmToMinutes("09:15")).toBe(555);
  });
});