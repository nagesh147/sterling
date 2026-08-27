import { describe, it, expect } from "vitest";
import {
  SLOT_HHMM,
  bandTitle,
  buildGrid,
  compareShot,
  formatPcr,
  hhmmToMinutes,
  pcrBand,
  putShare,
  roundPcr,
  slotLabel,
} from "./slots";
import { PCR_SNAPSHOT } from "./snapshot";

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

  it("matches the 27 Aug Nifty print on 19 of 25 published cells", () => {
    const grid = buildGrid(PCR_SNAPSHOT.NIFTY.marks, PCR_SNAPSHOT.NIFTY.latest, 15 * 60 + 30);
    const cmp = compareShot(grid);
    expect(cmp.total).toBe(25);
    expect(cmp.matched).toBeGreaterThanOrEqual(19);
    const exact: Record<string, number> = { "09:30": 0.7, "10:15": 0.64, "10:30": 0.63, "10:45": 0.62, "11:30": 0.56, "12:00": 0.56, "13:00": 0.6, "14:15": 0.57, "15:00": 0.6, "15:15": 0.59 };
    for (const hhmm of Object.keys(exact)) {
      const slot = grid.find((s) => s.hhmm === hhmm);
      expect(roundPcr(slot?.pcr ?? -1)).toBe(exact[hhmm]);
    }
  });

  it("keeps put share in (0,1) from PCR", () => {
    expect(Number(putShare(1)?.toFixed(2))).toBe(0.5);
    expect(putShare(0.59) ?? 0).toBeLessThan(0.4);
  });

  it("has a mark for every cash slot on the snapshot", () => {
    for (const id of ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "MIDCPNIFTY"] as const) {
      expect(PCR_SNAPSHOT[id].marks.length, id).toBe(26);
    }
    expect(hhmmToMinutes("09:15")).toBe(555);
  });
});
