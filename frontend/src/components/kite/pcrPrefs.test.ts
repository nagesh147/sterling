import { beforeEach, describe, expect, it } from "vitest";
import { DEFAULT_PREFS, PREF_KEY, loadPrefs, normalizeIndices, savePrefs } from "./pcrWidgets";

describe("PCR desk prefs", () => {
  beforeEach(() => localStorage.clear());

  it("round-trips a subset of indices", () => {
    savePrefs({ ...DEFAULT_PREFS, indices: ["NIFTY", "SENSEX"] });
    expect(loadPrefs().indices).toEqual(["NIFTY", "SENSEX"]);
  });

  it("keeps an empty index list instead of resetting to all", () => {
    savePrefs({ ...DEFAULT_PREFS, indices: [] });
    expect(loadPrefs().indices).toEqual([]);
  });

  it("defaults to every index when the field was never saved", () => {
    const { indices: _drop, ...legacy } = DEFAULT_PREFS;
    localStorage.setItem(PREF_KEY, JSON.stringify(legacy));
    expect(loadPrefs().indices).toEqual(DEFAULT_PREFS.indices);
  });

  it("drops unknown ids and keeps order of the desk", () => {
    expect(normalizeIndices(["SENSEX", "NOPE", "NIFTY"])).toEqual(["NIFTY", "SENSEX"]);
  });
});
