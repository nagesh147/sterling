/**
 * Artifact A5–A8 — gap call, muhurta clock, 30-minute execution grid, month projection.
 *
 * Purely astrological. No price, no OI, no candles. Same IST date always yields
 * the same book. Market hours 09:15–15:30 IST at Mumbai.
 *
 * `netResults` are irregular windows cut at hora / choghadiya / Rahu-Yamagandam /
 * lagna-sign / Abhijit — the actual muhurta clock. `slots` resample the same
 * sky onto a 13-slot 30-minute execution grid.
 */

import {
  KARANAS,
  NAKSHATRA_LORDS,
  NAKSHATRAS,
  TITHI_NAMES,
  UNDERLYINGS,
  WEEKDAY_LORDS,
  WEEKDAYS,
  YOGAS,
  type DayForecast,
  type DayPlaybook,
  type GapCall,
  type HoraInfo,
  type IndexPlay,
  type KalamFlag,
  type LiveNow,
  type MonthDay,
  type MonthProjection,
  type Panchang,
  type PlanetName,
  type PlanetPos,
  type Regime,
  type TradeAction,
  type TradeSide,
  type Underlying,
  type WindowSlot,
} from "./types";
import {
  SLOT_STARTS,
  clockFromMinutes,
  formatIstIsoDate,
  getIstParts,
  MARKET_CLOSE_MIN,
  MARKET_OPEN_MIN,
  minutesOfDay,
  utcFromIstParts,
} from "./time";
import {
  angularSep,
  isKendra,
  nakshatraIndex,
  nakshatraPada,
  planetByName,
  signName,
  snapshot,
  sunRiseSetIst,
} from "./ephemeris.ts";
import { holidayName, isMuhurat, isNseClosed, isNseHoliday, lastCompletedSessionIso, nextSessionIso } from "./holidays.ts";
import {
  aspectScore,
  choghadiyaAt,
  classifyThesis,
  dignityOf,
  dignityScore,
  eclipseCorridor,
  findAspects,
  horaModulation,
  isAbhijit,
  isGandanta,
  lagnaState,
  moonSpeedDegPerDay,
  mundaneHits,
  nodalAffliction,
  specialYogas,
  type Thesis,
} from "./factors.ts";

const HORA_CYCLE: PlanetName[] = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"];

const FIERY_NAK = new Set([0, 1, 2, 5, 9, 10, 18, 19, 24]);
const STABLE_NAK = new Set([3, 7, 11, 16, 20, 25]);
const VOL_NAK = new Set([5, 8, 14, 17, 18, 23]);

function clamp(n: number, a: number, b: number): number {
  return Math.max(a, Math.min(b, n));
}

function jdToDate(jd: number): Date {
  return new Date((jd - 2440587.5) * 86400000);
}

export function panchangAt(date: Date): { panchang: Panchang; planets: PlanetPos[]; lagna: number } {
  const snap = snapshot(date);
  const sun = planetByName(snap.planets, "Sun");
  const moon = planetByName(snap.planets, "Moon");
  const tithiSpan = ((moon.sidereal - sun.sidereal + 360) % 360) / 12;
  const tithiIndex0 = Math.floor(tithiSpan) % 30;
  const paksha: "Shukla" | "Krishna" = tithiIndex0 < 15 ? "Shukla" : "Krishna";
  const tithiInPaksha = tithiIndex0 % 15;
  const naks = nakshatraIndex(moon.sidereal);
  const yogaSpan = ((moon.sidereal + sun.sidereal) % 360) / (360 / 27);
  const yogaIndex = Math.floor(yogaSpan) % 27;
  const karanaIdx = Math.floor((((moon.sidereal - sun.sidereal + 360) % 360) / 6) % 60);
  let karana: string;
  if (karanaIdx === 0) karana = KARANAS[10];
  else if (karanaIdx >= 57) karana = KARANAS[Math.min(9, 7 + (karanaIdx - 57))];
  else karana = KARANAS[(karanaIdx - 1) % 7];

  const p = getIstParts(date);
  const rs = sunRiseSetIst(p.year, p.month, p.day);
  const rise = jdToDate(rs.rise);
  const set = jdToDate(rs.set);

  const panchang: Panchang = {
    weekday: WEEKDAYS[p.weekday],
    weekdayIndex: p.weekday,
    tithiIndex: tithiIndex0,
    tithiName: tithiInPaksha === 14 ? (paksha === "Shukla" ? "Purnima" : "Amavasya") : TITHI_NAMES[tithiInPaksha],
    paksha,
    nakshatraIndex: naks,
    nakshatra: NAKSHATRAS[naks],
    nakshatraPada: nakshatraPada(moon.sidereal),
    nakshatraLord: NAKSHATRA_LORDS[naks],
    yogaIndex,
    yoga: YOGAS[yogaIndex],
    karana,
    moonSign: moon.sign,
    sunSign: sun.sign,
    lagnaSign: signName(snap.lagnaSidereal),
    lagnaDegree: snap.lagnaSidereal % 30,
    sunriseIso: rise.toISOString(),
    sunsetIso: set.toISOString(),
  };
  return { panchang, planets: snap.planets, lagna: snap.lagnaSidereal };
}

export function horaAt(date: Date, panchang: Panchang): { lord: PlanetName; index: number; startsAt: string; endsAt: string } {
  const rise = new Date(panchang.sunriseIso);
  const set = new Date(panchang.sunsetIso);
  const dayMs = set.getTime() - rise.getTime();
  const horaLen = dayMs / 12;
  const elapsed = date.getTime() - rise.getTime();
  const idx = elapsed < 0 ? 0 : Math.min(11, Math.floor(elapsed / horaLen));
  const lord0 = WEEKDAY_LORDS[panchang.weekdayIndex];
  const start = HORA_CYCLE.indexOf(lord0);
  const lord = HORA_CYCLE[(start + idx) % 7];
  const starts = new Date(rise.getTime() + idx * horaLen);
  const ends = new Date(rise.getTime() + (idx + 1) * horaLen);
  return { lord, index: idx, startsAt: starts.toISOString(), endsAt: ends.toISOString() };
}

/** Day horas 0–11 sunrise→sunset; night horas 12–23 sunset→next sunrise, cycle continues. */
export function horaAround(date: Date): HoraInfo {
  const { panchang } = panchangAt(date);
  const rise = new Date(panchang.sunriseIso).getTime();
  const set = new Date(panchang.sunsetIso).getTime();
  const t = date.getTime();
  if (t >= rise && t < set) return horaAt(date, panchang);

  const p = getIstParts(date);
  let nightStart: number;
  let nightEnd: number;
  let dayLord0: PlanetName;
  if (t >= set) {
    const noon = utcFromIstParts(p.year, p.month, p.day, 12, 0, 0);
    const next = new Date(noon.getTime() + 24 * 60 * 60 * 1000);
    nightStart = set;
    nightEnd = new Date(panchangAt(next).panchang.sunriseIso).getTime();
    dayLord0 = WEEKDAY_LORDS[panchang.weekdayIndex];
  } else {
    const noon = utcFromIstParts(p.year, p.month, p.day, 12, 0, 0);
    const prev = new Date(noon.getTime() - 24 * 60 * 60 * 1000);
    const prevPan = panchangAt(prev).panchang;
    nightStart = new Date(prevPan.sunsetIso).getTime();
    nightEnd = rise;
    dayLord0 = WEEKDAY_LORDS[prevPan.weekdayIndex];
  }
  const horaLen = Math.max(1, nightEnd - nightStart) / 12;
  const idx = clamp(Math.floor((t - nightStart) / horaLen), 0, 11);
  const start = HORA_CYCLE.indexOf(dayLord0);
  const lord = HORA_CYCLE[(start + 12 + idx) % 7];
  const starts = new Date(nightStart + idx * horaLen);
  const ends = new Date(nightStart + (idx + 1) * horaLen);
  return { lord, index: 12 + idx, startsAt: starts.toISOString(), endsAt: ends.toISOString() };
}

function kalamAt(date: Date, panchang: Panchang): KalamFlag {
  const rise = new Date(panchang.sunriseIso).getTime();
  const set = new Date(panchang.sunsetIso).getTime();
  const part = (set - rise) / 8;
  const i = clamp(Math.floor((date.getTime() - rise) / part), 0, 7);
  const wd = panchang.weekdayIndex;
  const rahuPart = [7, 1, 6, 4, 5, 3, 2][wd];
  const yamaPart = [4, 3, 2, 1, 0, 6, 5][wd];
  const gulikaPart = [6, 5, 4, 3, 2, 1, 0][wd];
  return { rahu: i === rahuPart, yamagandam: i === yamaPart, gulika: i === gulikaPart };
}

function istMinutes(date: Date): number {
  const p = getIstParts(date);
  return minutesOfDay(p.hour, p.minute);
}

/** Muhurta cuts inside the cash session: opening range, hora, choghadiya/kalam, Abhijit, lagna-sign. */
function collectAstroCuts(year: number, month: number, day: number, panchang: Panchang): number[] {
  const openRangeEnd = MARKET_OPEN_MIN + 30;
  const cuts = new Set<number>([MARKET_OPEN_MIN, openRangeEnd, MARKET_CLOSE_MIN]);
  const add = (d: Date) => {
    const m = istMinutes(d);
    if (m > openRangeEnd && m < MARKET_CLOSE_MIN) cuts.add(m);
  };
  const rise = new Date(panchang.sunriseIso).getTime();
  const set = new Date(panchang.sunsetIso).getTime();
  const dayMs = Math.max(1, set - rise);
  for (let i = 0; i <= 12; i++) add(new Date(rise + (i * dayMs) / 12));
  for (let i = 0; i <= 8; i++) add(new Date(rise + (i * dayMs) / 8));
  const mid = (rise + set) / 2;
  add(new Date(mid - 12 * 60 * 1000));
  add(new Date(mid + 12 * 60 * 1000));
  let lastSign: number | null = null;
  for (let m = openRangeEnd; m <= MARKET_CLOSE_MIN; m += 1) {
    const dt = utcFromIstParts(year, month, day, Math.floor(m / 60), m % 60, 0);
    const { lagna } = panchangAt(dt);
    const s = Math.floor((((lagna % 360) + 360) % 360) / 30);
    if (lastSign !== null && s !== lastSign) cuts.add(m);
    lastSign = s;
  }
  return [...cuts].sort((a, b) => a - b);
}

function planetScore(name: PlanetName): { dir: number; vol: number } {
  switch (name) {
    case "Jupiter":
      return { dir: 2.2, vol: 0.4 };
    case "Venus":
      return { dir: 1.4, vol: 0.5 };
    case "Sun":
      return { dir: 1.6, vol: 0.8 };
    case "Mars":
      return { dir: 1.1, vol: 2.2 };
    case "Mercury":
      return { dir: 0.2, vol: 1.6 };
    case "Moon":
      return { dir: 0.3, vol: 1.4 };
    case "Saturn":
      return { dir: -2.0, vol: 0.7 };
    case "Rahu":
      return { dir: -0.6, vol: 2.4 };
    case "Ketu":
      return { dir: -1.2, vol: 1.8 };
  }
}

function elementDir(signIndex: number): number {
  const el = signIndex % 4;
  if (el === 0) return 1.1;
  if (el === 1) return 0.05;
  if (el === 2) return 0.35;
  return -0.85;
}

function signIndexOf(sidereal: number): number {
  return Math.floor((((sidereal % 360) + 360) % 360) / 30) % 12;
}

function scoreGap(
  panchang: Panchang,
  planets: PlanetPos[],
  lagna: number,
  underlying: Underlying,
): { dir: number; vol: number; reasons: string[]; thesis: Thesis } {
  const reasons: string[] = [];
  let dir = 0;
  let vol = 0.8;

  const wdLord = WEEKDAY_LORDS[panchang.weekdayIndex];
  const wdS = planetScore(wdLord);
  dir += wdS.dir * 0.35;
  vol += wdS.vol * 0.25;
  reasons.push(
    `${panchang.weekday} is ruled by ${wdLord} — ${wdS.dir >= 1 ? "constructive open" : wdS.dir <= -1 ? "heavy open" : "mixed open"}.`,
  );

  const t = panchang.tithiIndex % 15;
  const rikta = t === 3 || t === 8 || t === 13;
  if (rikta) {
    vol += 1.1;
    reasons.push(`${panchang.tithiName} is a Rikta tithi — empty for new longs. Fade the first impulse, don't gap-chase.`);
  } else if (panchang.paksha === "Shukla") {
    dir += 0.45;
    reasons.push("Shukla paksha (waxing Moon) favours buyers — mild gap-up bias.");
  } else {
    dir -= 0.45;
    reasons.push("Krishna paksha (waning Moon) favours sellers — mild gap-down bias.");
  }

  if (panchang.tithiName === "Purnima" || panchang.tithiName === "Amavasya") {
    vol += 1.6;
    reasons.push(`${panchang.tithiName} — full/new Moon, classic gap-and-whipsaw day.`);
  }
  if (t === 10 && !rikta) {
    dir += 0.4;
    reasons.push("Ekadashi supports a cleaner directional drive.");
  }

  const naks = panchang.nakshatraIndex;
  if (FIERY_NAK.has(naks)) {
    dir += 0.45;
    vol += 0.7;
    reasons.push(`Moon in ${panchang.nakshatra} (Pada ${panchang.nakshatraPada}) — fiery, trend-seeking.`);
  } else if (STABLE_NAK.has(naks)) {
    vol -= 0.45;
    reasons.push(`Moon in ${panchang.nakshatra} — steadier tape, smaller gap.`);
  }
  if (VOL_NAK.has(naks)) {
    vol += 1.0;
    reasons.push(`${panchang.nakshatra} is a volatile nakshatra — expect a fast first 15 minutes.`);
  }

  const moon = planetByName(planets, "Moon");
  const sun = planetByName(planets, "Sun");
  const mars = planetByName(planets, "Mars");
  const jup = planetByName(planets, "Jupiter");
  const sat = planetByName(planets, "Saturn");
  const rahu = planetByName(planets, "Rahu");
  const mer = planetByName(planets, "Mercury");

  const aspects = findAspects(planets);
  const ascore = aspectScore(aspects);
  dir += ascore.dir;
  vol += ascore.vol;
  reasons.push(...ascore.reasons);

  const dscore = dignityScore(planets);
  dir += dscore.dir;
  vol += dscore.vol;
  reasons.push(...dscore.reasons);

  const ecl = eclipseCorridor(planets);
  if (ecl.active && ecl.note) {
    vol += 1.5;
    dir *= 0.65;
    reasons.push(ecl.note);
  }

  if (isGandanta(moon.sidereal) || isGandanta(lagna)) {
    vol += 1.3;
    reasons.push(
      isGandanta(moon.sidereal)
        ? "Moon in gandanta — junction of water and fire. Opening range is a trap."
        : "Open lagna in gandanta — first 15 minutes will hunt both sides.",
    );
  }

  const speed = moonSpeedDegPerDay(new Date(panchang.sunriseIso));
  if (speed >= 14.2) {
    vol += 0.7;
    reasons.push(`Fast Moon (${speed.toFixed(1)}°/day) — tape covers distance, don't fade the first hour.`);
  } else if (speed <= 12.2) {
    vol -= 0.25;
    dir *= 0.85;
    reasons.push(`Slow Moon (${speed.toFixed(1)}°/day) — sticky, range-bound open.`);
  }

  const yogas = specialYogas(panchang, planets, lagna);
  for (const y of yogas.slice(0, 2)) reasons.push(y);
  if (yogas.some((y) => y.startsWith("Gajakesari"))) {
    const sep = angularSep(moon.sidereal, jup.sidereal);
    dir += Math.abs(sep - 180) < 12 ? 0.2 : 0.7;
  }
  if (yogas.some((y) => y.startsWith("Kemadruma"))) vol += 0.45;
  if (yogas.some((y) => y.startsWith("Mangal-Rahu"))) {
    vol += 1.2;
    dir -= 0.4;
  }
  if (yogas.some((y) => y.startsWith("Shani-Rahu"))) dir -= 0.9;
  if (yogas.some((y) => y.startsWith("Guru-Mangala"))) {
    dir += 0.5;
    vol += 0.6;
  }

  for (const n of mundaneHits(planets)) {
    reasons.push(n);
    if (n.includes("shock") || n.includes("pressure")) {
      vol += 0.8;
      dir -= 0.45;
    }
    if (n.includes("sponsorship") || n.includes("constructive")) dir += 0.6;
  }

  dir += elementDir(moon.signIndex) * 0.55;
  dir += elementDir(signIndexOf(lagna)) * 0.4;

  const marsMoon = angularSep(mars.sidereal, moon.sidereal);
  if (marsMoon < 12 || Math.abs(marsMoon - 180) < 10) {
    vol += 1.6;
    dir += marsMoon < 12 ? 0.4 : -0.3;
    reasons.push(`Mars ${marsMoon < 12 ? "conjunct" : "opposite"} Moon — opening impulse will be sharp.`);
  }

  const lagnaSign = signIndexOf(lagna);
  if (isKendra(lagnaSign, jup.signIndex) || isKendra(lagnaSign, planetByName(planets, "Venus").signIndex)) {
    dir += 0.7;
    reasons.push("Jupiter/Venus occupy a kendra from the 09:15 lagna — a bid can appear.");
  }
  if (isKendra(lagnaSign, sat.signIndex) || isKendra(lagnaSign, rahu.signIndex)) {
    dir -= 0.85;
    vol += 0.5;
    reasons.push("Saturn/Rahu on a kendra from the open lagna — supply at the bell.");
  }

  const lag = lagnaState(planets, lagna);
  if (lag.note) reasons.push(lag.note);

  if (mer.retrograde) {
    vol += 1.1;
    dir *= 0.7;
    reasons.push("Mercury retrograde — gap often fades inside the first hour.");
  }
  if (angularSep(mer.sidereal, sun.sidereal) < 8.5) {
    vol += 0.6;
    reasons.push("Mercury combust — mixed tape, fade the first spike.");
  }
  if (nodalAffliction(planets, ["Mercury", "Sun"])) {
    reasons.push("Sun/Mercury under Rahu — news open, the first tick is the trap.");
  }

  const yogaBad = new Set(["Vyatipata", "Vaidhriti", "Vajra", "Vyaghata", "Parigha", "Shoola", "Ganda", "Atiganda"]);
  if (yogaBad.has(panchang.yoga)) {
    vol += 0.9;
    dir -= 0.3;
    reasons.push(`${panchang.yoga} yoga is inauspicious for a clean trend — two-way trade.`);
  }
  if (panchang.karana === "Vishti") {
    vol += 0.7;
    reasons.push("Bhadra (Vishti) karana — avoid chasing the opening tick.");
  } else if (panchang.karana === "Garaja") {
    vol += 0.35;
    reasons.push("Garaja karana — unsettled, leaving not settling. Don't marry the first side.");
  }

  reasons.push(
    `Open lagna is ${panchang.lagnaSign} ${panchang.lagnaDegree.toFixed(1)}° — ${elementDir(lagnaSign) > 0.5 ? "fire/air, expansion" : elementDir(lagnaSign) < 0 ? "water, absorption" : "earth, digestion"}.`,
  );

  const thesis = classifyThesis({
    panchang,
    planets,
    lagna,
    underlying,
    baseDir: dir,
    baseVol: vol,
    yogas,
    eclipse: ecl.active,
  });

  const uniq: string[] = [];
  for (const r of [lag.note, thesis.sectorNote, thesis.note, ...reasons]) {
    if (r && !uniq.includes(r)) uniq.push(r);
  }
  return { dir: thesis.dir, vol: thesis.vol, reasons: uniq.slice(0, 10), thesis };
}

function volLabel(vol: number, thesis: Thesis, panchang: Panchang, eclipse: boolean, gandanta: boolean): GapCall["volatility"] {
  const fullEmpty = panchang.tithiName === "Purnima" || panchang.tithiName === "Amavasya";
  if (eclipse || gandanta) return "extreme";
  if (fullEmpty && vol >= 3.8) return "extreme";
  if (vol >= 5.5) return "extreme";
  if (vol >= 3.0 || thesis.kind === "fade") return "high";
  if (vol >= 1.8) return "medium";
  return "low";
}

function gapFromDir(dir: number, thesis: Thesis): GapCall["kind"] {
  const threshold = thesis.kind === "fade" ? 2.05 : thesis.vol >= 3.2 ? 1.25 : 1.55;
  if (dir >= threshold) return "up";
  if (dir <= -threshold) return "down";
  return "flat";
}

function openAction(kind: GapCall["kind"], vol: GapCall["volatility"], thesis: Thesis): TradeAction {
  if (thesis.fadeOpen || vol === "extreme") return "WAIT";
  if (kind === "up") return vol === "high" ? "SCALP CE" : "BUY CE";
  if (kind === "down") return vol === "high" ? "SCALP PE" : "BUY PE";
  if (vol === "high") return "STRADDLE";
  return "IRON FLY";
}

function buildGap(
  panchang: Panchang,
  planets: PlanetPos[],
  lagna: number,
  underlying: Underlying,
  horaLord: PlanetName,
  scored: { dir: number; vol: number; reasons: string[]; thesis: Thesis },
): GapCall {
  const { dir, vol, reasons, thesis } = scored;
  const kind = gapFromDir(dir, thesis);
  const ecl = eclipseCorridor(planets);
  const moon = planetByName(planets, "Moon");
  const gandanta = isGandanta(moon.sidereal) || isGandanta(lagna);
  const volatility = volLabel(vol, thesis, panchang, ecl.active, gandanta);
  const confidence = clamp(
    Math.round(44 + Math.abs(dir) * 10 + (vol > 2 ? 4 : 0) - (thesis.kind === "fade" ? 6 : 0)),
    52,
    thesis.kind === "fade" ? 76 : 94,
  );
  const bias: GapCall["bias"] = dir > 0.7 ? "bullish" : dir < -0.7 ? "bearish" : "neutral";
  const label = kind === "up" ? "GAP UP" : kind === "down" ? "GAP DOWN" : "FLAT / INSIDE";
  const action = openAction(kind, volatility, thesis);
  const yogas = specialYogas(panchang, planets, lagna);
  const residual = dir < -0.45 ? "PE" : dir > 0.45 ? "CE" : "both wings";
  const firstHourNote = thesis.fadeOpen
    ? `Do not chase 09:15. Sit through the first hora and Yamagandam. Residual after the trap-open is ${residual}. If the first 15-minute close disagrees, still do not flip — this is a ${thesis.kind} session.`
    : kind === "flat"
      ? "Open inside yesterday — sell the wings, fade the first spike back to VWAP."
      : kind === "up"
        ? `Gap-up in ${horaLord} hora: buy CE only on a hold above the opening 5-minute low. PE only if it fails in 15 minutes.`
        : `Gap-down in ${horaLord} hora: buy PE on a hold below the opening 5-minute high. CE only if it reclaims immediately.`;

  const summary =
    thesis.kind === "fade"
      ? `${underlying} is a fade session into ${horaLord} hora. ${thesis.note} First trade WAIT.`
      : kind === "up"
        ? `${underlying} is astrologically set to open higher into ${horaLord} hora. ${volatility === "high" || volatility === "extreme" ? "The gap can be violent — size down." : "A constructive gap, not a trap, if the first 5-minute hold confirms."}`
        : kind === "down"
          ? `${underlying} is astrologically set to open lower into ${horaLord} hora. ${volatility === "high" || volatility === "extreme" ? "Respect the flush — don't catch the first knife with CE." : "A heavy open; PE is the default until hora flips."}`
          : `${underlying} is astrologically set to open flat-to-inside into ${horaLord} hora. Two-way trade. Premium sellers have the edge until a hora shift.`;

  return {
    kind,
    label,
    confidence,
    volatility,
    bias,
    openAction: action,
    summary,
    reasons,
    firstHourNote,
    horaAtOpen: horaLord,
    yogas,
    eclipse: ecl.active,
    gandanta,
    thesis: thesis.kind,
    thesisNote: thesis.note,
    sectorNote: thesis.sectorNote,
  };
}

function regimeFrom(dir: number, vol: number): Regime {
  const hot = vol >= 2.4;
  if (dir >= 2.4) return hot ? "Volatile Positive" : "Strong Positive";
  if (dir >= 1.2) return hot ? "Volatile Positive" : "Positive";
  if (dir >= 0.45) return hot ? "Sideways/Volatile" : "Sideways to Positive";
  if (dir <= -2.4) return hot ? "Volatile Negative" : "Strong Negative";
  if (dir <= -1.2) return hot ? "Volatile Negative" : "Negative";
  if (dir <= -0.45) return hot ? "Sideways/Volatile" : "Sideways to Negative";
  return "Sideways/Volatile";
}

function actionFrom(
  regime: Regime,
  kalam: KalamFlag,
  hora: PlanetName,
  thesis: Thesis,
  opts: { forceWait: boolean; abhijit: boolean },
): { action: TradeAction; side: TradeSide; suggestion: string } {
  if (opts.forceWait) {
    return {
      action: "WAIT",
      side: "WAIT",
      suggestion: `${thesis.kind === "fade" ? "Fade open" : "Unstable open"} — no fresh entries this slot. Let the first hora finish, then take the residual.`,
    };
  }
  if (kalam.rahu) {
    return {
      action: "AVOID",
      side: "WAIT",
      suggestion: "Rahu Kalam — no fresh entries. If in profit, trail. If flat, sit on hands.",
    };
  }
  if (kalam.yamagandam) {
    return {
      action: "WAIT",
      side: "WAIT",
      suggestion: "Yamagandam — no new positional trades. Trail what you have, reload next slot.",
    };
  }

  if (opts.abhijit && (thesis.kind === "fade" || thesis.kind === "trend-down" || thesis.kind === "trend-up")) {
    if (thesis.dir < -0.45) {
      return {
        action: "BOOK PE",
        side: "PE",
        suggestion: "Abhijit on a residual-PE day — book 50–70% of PE, do not add CE.",
      };
    }
    if (thesis.dir > 0.45) {
      return {
        action: "BOOK CE",
        side: "CE",
        suggestion: "Abhijit on a residual-CE day — book 50–70% of CE, do not add PE.",
      };
    }
  }

  let traded: { action: TradeAction; side: TradeSide; suggestion: string };
  switch (regime) {
    case "Strong Positive":
      traded = { action: "BUY CE", side: "CE", suggestion: `Ride ${hora} hora. Buy ATM/ITM CE, trail. Do not average PE.` };
      break;
    case "Positive":
      traded = { action: "BUY CE", side: "CE", suggestion: "Buy CE on any 5-min dip. Book 40–50% at 1:1, trail the rest." };
      break;
    case "Volatile Positive":
      traded = { action: "SCALP CE", side: "CE", suggestion: "Fast CE scalps only. Tight stop under the prior 5-min low. No overnight." };
      break;
    case "Sideways to Positive":
      traded = { action: "SCALP CE", side: "CE", suggestion: "Range with a green tilt. Small CE, or a bull call debit spread." };
      break;
    case "Sideways/Volatile":
      traded = {
        action: thesis.kind === "fade" ? (thesis.dir < 0 ? "SCALP PE" : thesis.dir > 0 ? "SCALP CE" : "STRADDLE") : "STRADDLE",
        side: thesis.kind === "fade" ? (thesis.dir < 0 ? "PE" : thesis.dir > 0 ? "CE" : "BOTH") : "BOTH",
        suggestion:
          thesis.kind === "fade"
            ? `Chop inside a fade. Prefer a small ${thesis.dir < 0 ? "PE" : "CE"} scalp, not a new trend.`
            : "Both sides live. Prefer a long straddle/strangle, or stay out if you only play direction.",
      };
      break;
    case "Sideways to Negative":
      traded = { action: "SCALP PE", side: "PE", suggestion: "Range with a red tilt. Small PE, or a bear put debit spread." };
      break;
    case "Volatile Negative":
      traded = { action: "SCALP PE", side: "PE", suggestion: "Fast PE scalps. Tight stop above the prior 5-min high. Don't fade with CE." };
      break;
    case "Negative":
      traded = { action: "BUY PE", side: "PE", suggestion: "Buy PE on any 5-min pop. Book 40–50% at 1:1, trail the rest." };
      break;
    case "Strong Negative":
      traded = { action: "BUY PE", side: "PE", suggestion: `Ride ${hora} hora. Buy ATM/ITM PE, trail. Do not average CE.` };
      break;
  }

  if (kalam.gulika && traded.action === "BUY CE") {
    traded = { action: "SCALP CE", side: "CE", suggestion: "Gulika — no new positional CE. Scalp only, tight stop." };
  }
  if (kalam.gulika && traded.action === "BUY PE") {
    traded = { action: "SCALP PE", side: "PE", suggestion: "Gulika — no new positional PE. Scalp only, tight stop." };
  }

  if (thesis.kind === "trend-up" && traded.side === "PE" && traded.action !== "WAIT") {
    return {
      action: "HOLD CE",
      side: "CE",
      suggestion: `${hora} hora is malefic on a trend-up day — hold/trail CE, do not start a PE trend.`,
    };
  }
  if (thesis.kind === "trend-down" && traded.side === "CE" && traded.action !== "WAIT") {
    return {
      action: "HOLD PE",
      side: "PE",
      suggestion: `${hora} hora is benefic on a trend-down day — scalp the bounce or hold PE, do not start a CE trend.`,
    };
  }
  return traded;
}

function productFor(underlying: Underlying, side: TradeSide, _vol: number): string {
  if (side === "WAIT") return "No contract";
  if (side === "BOTH") return `${underlying} ATM straddle`;
  return `${underlying} ATM ${side === "CE" ? "CE" : "PE"}`;
}

function slotWhy(
  hora: PlanetName,
  lagna: string,
  kalam: KalamFlag,
  regime: Regime,
  nak: string,
  cho: string,
  abhijit: boolean,
): string {
  const bits: string[] = [`${hora} hora`, `lagna ${lagna}`, `Moon ${nak}`, `${cho} choghadiya`];
  if (kalam.rahu) bits.push("Rahu Kalam");
  if (kalam.yamagandam) bits.push("Yamagandam");
  if (kalam.gulika) bits.push("Gulika");
  if (abhijit) bits.push("Abhijit");
  bits.push(regime);
  return bits.join(" · ");
}

function scoreWindow(
  hora: PlanetName,
  panchang: Panchang,
  lagna: number,
  kalam: KalamFlag,
  cho: { kind: "good" | "move" | "bad" },
  abhijit: boolean,
  thesis: Thesis,
): { dir: number; vol: number } {
  const hs = horaModulation(hora);
  const scale = thesis.kind === "fade" || thesis.kind === "chop" ? 0.4 : 0.9;
  let dir = thesis.dir + hs.dir * scale;
  let vol = Math.max(0.55, thesis.vol * 0.5 + hs.vol);
  dir += elementDir(signIndexOf(lagna)) * 0.2;
  if (FIERY_NAK.has(panchang.nakshatraIndex)) vol += 0.25;
  if (VOL_NAK.has(panchang.nakshatraIndex)) vol += 0.35;
  if (STABLE_NAK.has(panchang.nakshatraIndex)) vol -= 0.2;
  if (kalam.rahu) {
    vol += 1.0;
    dir *= 0.3;
  }
  if (kalam.yamagandam) {
    vol += 0.45;
    dir *= 0.4;
  }
  if (kalam.gulika) dir -= 0.15;
  if (cho.kind === "good") dir += thesis.kind === "fade" ? 0.12 : 0.4;
  if (cho.kind === "move") vol += 0.35;
  if (cho.kind === "bad") {
    dir *= 0.88;
    vol += 0.25;
  }
  if (abhijit) dir *= thesis.kind === "fade" ? 0.8 : 1.15;
  return { dir, vol };
}

function applyHoldBook(slots: WindowSlot[]): WindowSlot[] {
  return slots.map((s, i) => {
    const prev = slots[i - 1];
    if (!prev) return s;
    if (s.action === "AVOID" || s.action === "WAIT" || s.action === "STRADDLE" || s.action === "IRON FLY") return s;
    if (prev.side === "CE" && s.side === "CE" && prev.strength > s.strength + 10) {
      const action: WindowSlot["action"] = s.strength < 58 ? "BOOK CE" : "HOLD CE";
      return {
        ...s,
        action,
        suggestion:
          action === "BOOK CE"
            ? "Edge is fading. Book 50–70% of CE, trail the rest. No add."
            : "Same side, weaker. Hold CE, trail. Do not add size.",
      };
    }
    if (prev.side === "PE" && s.side === "PE" && prev.strength > s.strength + 10) {
      const action: WindowSlot["action"] = s.strength < 58 ? "BOOK PE" : "HOLD PE";
      return {
        ...s,
        action,
        suggestion:
          action === "BOOK PE"
            ? "Edge is fading. Book 50–70% of PE, trail the rest. No add."
            : "Same side, weaker. Hold PE, trail. Do not add size.",
      };
    }
    return s;
  });
}

export function forecastDay(date: Date, underlying: Underlying = "NIFTY", now: Date = new Date()): DayForecast {
  const p = getIstParts(date);
  const open = utcFromIstParts(p.year, p.month, p.day, 9, 0, 0);
  const bell = utcFromIstParts(p.year, p.month, p.day, 9, 15, 0);
  const { panchang, planets, lagna } = panchangAt(open);
  const horaOpen = horaAt(bell, panchang);
  const scored = scoreGap(panchang, planets, lagna, underlying);
  const gap = buildGap(panchang, planets, lagna, underlying, horaOpen.lord, scored);
  const thesis = scored.thesis;
  const iso = formatIstIsoDate(open);
  const nowParts = getIstParts(now);
  const nowMin = minutesOfDay(nowParts.hour, nowParts.minute);
  const sameDay = nowParts.year === p.year && nowParts.month === p.month && nowParts.day === p.day;

  const buildRange = (fromMin: number, toMin: number): WindowSlot => {
    const midMin = Math.floor((fromMin + toMin) / 2);
    const mid = utcFromIstParts(p.year, p.month, p.day, Math.floor(midMin / 60), midMin % 60, 0);
    const { panchang: pan, lagna: lag } = panchangAt(mid);
    const hora = horaAt(mid, pan);
    const kalam = kalamAt(mid, pan);
    const cho = choghadiyaAt(mid, pan);
    const abhijit = isAbhijit(mid, pan);
    const scoredSlot = scoreWindow(hora.lord, pan, lag, kalam, cho, abhijit, thesis);
    const regime = regimeFrom(scoredSlot.dir, scoredSlot.vol);
    const forceWait = fromMin === MARKET_OPEN_MIN && (gap.openAction === "WAIT" || thesis.fadeOpen);
    const traded = actionFrom(regime, kalam, hora.lord, thesis, { forceWait, abhijit });
    const isLive = sameDay && nowMin >= fromMin && nowMin < toMin;
    const isPast = sameDay ? nowMin >= toMin : now.getTime() > mid.getTime();
    const strength = clamp(Math.round(36 + Math.abs(scoredSlot.dir) * 14 + scoredSlot.vol * 6), 40, 98);
    return {
      date: iso,
      from: clockFromMinutes(fromMin),
      to: clockFromMinutes(toMin),
      fromMin,
      toMin,
      hora: hora.lord,
      lagna: signName(lag),
      nakshatra: pan.nakshatra,
      regime,
      action: traded.action,
      side: traded.side,
      product: productFor(underlying, traded.side, scoredSlot.vol),
      suggestion: traded.suggestion,
      strength,
      confidence: clamp(Math.round(50 + Math.abs(scoredSlot.dir) * 10), 48, 92),
      kalam,
      why: slotWhy(hora.lord, signName(lag), kalam, regime, pan.nakshatra, cho.name, abhijit),
      isLive,
      isPast,
      choghadiya: cho.name,
      choghadiyaKind: cho.kind,
      abhijit,
    };
  };

  const raw: WindowSlot[] = SLOT_STARTS.map(([h, m], i) => {
    const fromMin = minutesOfDay(h, m);
    const next = SLOT_STARTS[i + 1];
    const toMin = next ? minutesOfDay(next[0], next[1]) : MARKET_CLOSE_MIN;
    return buildRange(fromMin, toMin);
  });

  const cuts = collectAstroCuts(p.year, p.month, p.day, panchang);
  const rawNet: WindowSlot[] = [];
  for (let i = 0; i < cuts.length - 1; i++) {
    rawNet.push(buildRange(cuts[i], cuts[i + 1]));
  }

  const slots = applyHoldBook(raw);
  const netResults = applyHoldBook(rawNet);

  const ceSlots = slots.filter((s) => s.side === "CE" && s.action !== "AVOID" && s.action !== "WAIT");
  const peSlots = slots.filter((s) => s.side === "PE" && s.action !== "AVOID" && s.action !== "WAIT");
  const bestCe = [...ceSlots].sort((a, b) => b.strength - a.strength)[0] ?? null;
  const bestPe = [...peSlots].sort((a, b) => b.strength - a.strength)[0] ?? null;
  const avoid = slots.filter((s) => s.action === "AVOID" || s.kalam.rahu);
  const closeBias = regimeFrom(thesis.dir, Math.min(thesis.vol, 2.2));

  const headline = `${gap.label} · ${thesis.kind} · ${gap.volatility} vol · ${horaOpen.lord} hora at the bell · first trade ${gap.openAction}. Best CE ${bestCe ? `${bestCe.from}–${bestCe.to}` : "none"}. Best PE ${bestPe ? `${bestPe.from}–${bestPe.to}` : "none"}.`;

  const playbook: DayPlaybook = {
    date: iso,
    weekday: panchang.weekday,
    underlying,
    gap,
    panchang,
    bestCe,
    bestPe,
    avoid,
    closeBias,
    headline,
    horaAtOpen: horaOpen.lord,
    thesis: thesis.kind,
  };

  return {
    date: iso,
    underlying,
    generatedAt: now.toISOString(),
    panchang,
    planets,
    gap,
    playbook,
    slots,
    netResults,
    aspects: findAspects(planets),
    dignities: planets.map(dignityOf),
  };
}

export function forecastMonth(year: number, month: number, underlying: Underlying, today = new Date()): MonthProjection {
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const todayIso = formatIstIsoDate(today);
  const days: MonthDay[] = [];
  let gapUp = 0;
  let gapDown = 0;
  let gapFlat = 0;
  let bullishDays = 0;
  let bearishDays = 0;
  let tradingDays = 0;

  for (let d = 1; d <= lastDay; d++) {
    const dt = utcFromIstParts(year, month, d, 9, 0, 0);
    const iso = `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const wd = getIstParts(dt).weekday;
    const weekend = wd === 0 || wd === 6;
    const hol = holidayName(iso);
    const muhurat = isMuhurat(iso);
    if (weekend || (hol && !muhurat)) {
      days.push({
        date: iso,
        weekday: WEEKDAYS[wd],
        isWeekend: weekend,
        isHoliday: Boolean(hol),
        holidayName: hol,
        isToday: iso === todayIso,
        gap: null,
        gapLabel: hol ? hol : "Weekend",
        bias: null,
        volatility: null,
        regime: null,
        openAction: null,
        confidence: 0,
        note: hol ?? (weekend ? "Market closed" : ""),
      });
      continue;
    }
    const book = forecastDay(dt, underlying, dt);
    tradingDays += 1;
    if (book.gap.kind === "up") gapUp += 1;
    else if (book.gap.kind === "down") gapDown += 1;
    else gapFlat += 1;
    if (book.gap.bias === "bullish") bullishDays += 1;
    if (book.gap.bias === "bearish") bearishDays += 1;
    days.push({
      date: iso,
      weekday: WEEKDAYS[wd],
      isWeekend: false,
      isHoliday: false,
      holidayName: muhurat ? "Muhurat session" : undefined,
      isToday: iso === todayIso,
      gap: book.gap.kind,
      gapLabel: book.gap.label,
      bias: book.gap.bias,
      volatility: book.gap.volatility,
      regime: book.playbook.closeBias,
      openAction: book.gap.openAction,
      confidence: book.gap.confidence,
      note: book.gap.summary,
    });
  }

  const monthName = new Date(Date.UTC(year, month - 1, 1)).toLocaleString("en-IN", { month: "long", timeZone: "UTC" });
  const lean =
    bullishDays > bearishDays + 2
      ? "The month leans bullish — CE is the default on strength days."
      : bearishDays > bullishDays + 2
        ? "The month leans bearish — PE is the default on pressure days."
        : "The month is two-sided. Trade the day's gap, not a monthly opinion.";
  const summary = `${tradingDays} sessions · ${gapUp} gap-up · ${gapFlat} flat · ${gapDown} gap-down. ${lean}`;

  return {
    year,
    month,
    label: `${monthName} ${year}`,
    days,
    tradingDays,
    gapUp,
    gapDown,
    gapFlat,
    bullishDays,
    bearishDays,
    summary,
  };
}

export function isTradingDay(iso: string, weekday: number): boolean {
  if (weekday === 0 || weekday === 6) return false;
  if (isMuhurat(iso)) return true;
  return !isNseHoliday(iso);
}

function isoParts(iso: string): { y: number; m: number; d: number } {
  const [y, m, d] = iso.split("-").map(Number);
  return { y, m, d };
}

function utcAtMin(iso: string, min: number): Date {
  const { y, m, d } = isoParts(iso);
  return utcFromIstParts(y, m, d, Math.floor(min / 60), min % 60, 0);
}

function sideOf(action: TradeAction): TradeSide {
  if (action.includes("CE") && action.includes("PE")) return "BOTH";
  if (action.includes("CE")) return "CE";
  if (action.includes("PE")) return "PE";
  if (action === "STRADDLE" || action === "IRON FLY") return "BOTH";
  return "WAIT";
}

/** Current sky + the cash window that is live, about to open, or next. */
export function liveNow(now: Date, underlying: Underlying): LiveNow {
  const p = getIstParts(now);
  const todayIso = formatIstIsoDate(now);
  const nowMin = minutesOfDay(p.hour, p.minute);
  const todayClosed = isNseClosed(todayIso);
  const inCash = !todayClosed && nowMin >= MARKET_OPEN_MIN && nowMin < MARKET_CLOSE_MIN;
  const preOpen = !todayClosed && nowMin < MARKET_OPEN_MIN;
  const phase: LiveNow["phase"] = inCash ? "live" : preOpen ? "pre" : todayClosed ? "closed" : "post";
  const nextOpenIso = nextSessionIso(now);
  const sessionIso = phase === "post" ? lastCompletedSessionIso(now) : nextOpenIso;
  const { y, m, d } = isoParts(sessionIso);
  const sessionDate = utcFromIstParts(y, m, d, 9, 0, 0);
  const book = forecastDay(sessionDate, underlying, now);
  const sky = panchangAt(now);
  const hora = horaAround(now);
  const riseMs = new Date(sky.panchang.sunriseIso).getTime();
  const setMs = new Date(sky.panchang.sunsetIso).getTime();
  const daySky = now.getTime() >= riseMs && now.getTime() < setMs;
  const cho = daySky
    ? choghadiyaAt(now, sky.panchang)
    : { name: "Night" as const, kind: "move" as const, index: -1 };
  const kalam = daySky ? kalamAt(now, sky.panchang) : { rahu: false, yamagandam: false, gulika: false };

  let window: WindowSlot | null = null;
  let next: WindowSlot | null = null;
  if (inCash) {
    const i = book.netResults.findIndex((s) => s.isLive);
    window = i >= 0 ? book.netResults[i] : book.slots.find((s) => s.isLive) ?? null;
    next = i >= 0 ? (book.netResults[i + 1] ?? null) : book.netResults[0] ?? null;
  } else if (phase === "post") {
    const { y: ny, m: nm, d: nd } = isoParts(nextOpenIso);
    next = forecastDay(utcFromIstParts(ny, nm, nd, 9, 0, 0), underlying, now).netResults[0] ?? null;
  } else {
    next = book.netResults[0] ?? null;
  }

  const last = book.netResults[book.netResults.length - 1] ?? null;
  const play = window ? window.action : phase === "post" ? (last?.action ?? "WAIT") : book.gap.openAction;
  const suggestion = window ? window.suggestion : phase === "post" ? book.playbook.headline : book.gap.summary;
  const side = window ? window.side : phase === "post" ? (last?.side ?? "WAIT") : sideOf(play);

  return {
    iso: todayIso,
    sessionIso,
    weekday: sky.panchang.weekday,
    phase,
    hora,
    lagnaSign: sky.panchang.lagnaSign,
    lagnaDegree: sky.panchang.lagnaDegree,
    nakshatra: sky.panchang.nakshatra,
    tithiName: sky.panchang.tithiName,
    paksha: sky.panchang.paksha,
    yoga: sky.panchang.yoga,
    karana: sky.panchang.karana,
    choghadiya: cho.name,
    choghadiyaKind: cho.kind,
    kalam,
    window,
    next,
    play,
    side,
    suggestion,
    regime: window ? window.regime : book.playbook.closeBias,
    gap: book.gap,
    thesis: book.gap.thesis,
    bellMs: utcAtMin(nextOpenIso, MARKET_OPEN_MIN).getTime(),
    closeMs: utcAtMin(inCash || phase === "post" ? todayIso : sessionIso, MARKET_CLOSE_MIN).getTime(),
    nextOpenIso,
  };
}

/** Current play on every index from the same clock — Nifty vs Bank split is the tell. */
export function liveBoard(now: Date): IndexPlay[] {
  return UNDERLYINGS.map((u) => {
    const s = liveNow(now, u.id);
    return { id: u.id, play: s.play, side: s.side, thesis: s.thesis };
  });
}
