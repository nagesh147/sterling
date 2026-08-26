/**
 * Artifact A5–A8 — gap call, 30-minute clock, trade language, month projection.
 *
 * Purely astrological. No price, no OI, no candles. Same IST date always yields
 * the same book. Market hours 09:15–15:30 IST at Mumbai.
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
  type KalamFlag,
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
  julianDate,
  MARKET_CLOSE_MIN,
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
  sunRiseSet,
} from "./ephemeris";
import { holidayName, isMuhurat, isNseHoliday } from "./holidays";
import {
  aspectScore,
  choghadiyaAt,
  dignityOf,
  dignityScore,
  eclipseCorridor,
  findAspects,
  isAbhijit,
  isGandanta,
  moonSpeedDegPerDay,
  mundaneHits,
  specialYogas,
} from "./factors";

const HORA_CYCLE: PlanetName[] = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"];

const BULLISH: PlanetName[] = ["Sun", "Mars", "Jupiter", "Venus"];
const BEARISH: PlanetName[] = ["Saturn", "Rahu", "Ketu"];
const CHOPPY: PlanetName[] = ["Mercury", "Moon"];

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
  const noon = utcFromIstParts(p.year, p.month, p.day, 12, 0, 0);
  const rs = sunRiseSet(julianDate(noon));
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

function scoreGap(panchang: Panchang, planets: PlanetPos[], lagna: number): { dir: number; vol: number; reasons: string[] } {
  const reasons: string[] = [];
  let dir = 0;
  let vol = 0.8;

  const wdLord = WEEKDAY_LORDS[panchang.weekdayIndex];
  const wdS = planetScore(wdLord);
  dir += wdS.dir * 0.55;
  vol += wdS.vol * 0.35;
  reasons.push(
    `${panchang.weekday} is ruled by ${wdLord} — ${wdS.dir >= 1 ? "constructive open" : wdS.dir <= -1 ? "heavy open" : "mixed open"}.`,
  );

  if (panchang.paksha === "Shukla") {
    dir += 1.35;
    reasons.push("Shukla paksha (waxing Moon) favours buyers — gap-up bias.");
  } else {
    dir -= 1.35;
    reasons.push("Krishna paksha (waning Moon) favours sellers — gap-down bias.");
  }

  const t = panchang.tithiIndex % 15;
  if (t === 3 || t === 8 || t === 13) {
    vol += 1.4;
    reasons.push(`${panchang.tithiName} is a Rikta tithi — wide, unreliable opening range.`);
  }
  if (panchang.tithiName === "Purnima" || panchang.tithiName === "Amavasya") {
    vol += 1.8;
    reasons.push(`${panchang.tithiName} — full/new Moon, classic gap-and-whipsaw day.`);
  }
  if (t === 10) {
    dir += 0.5;
    reasons.push("Ekadashi supports a cleaner directional drive.");
  }

  const naks = panchang.nakshatraIndex;
  if (FIERY_NAK.has(naks)) {
    dir += 0.7;
    vol += 0.9;
    reasons.push(`Moon in ${panchang.nakshatra} (Pada ${panchang.nakshatraPada}) — fiery, trend-seeking.`);
  } else if (STABLE_NAK.has(naks)) {
    vol -= 0.5;
    reasons.push(`Moon in ${panchang.nakshatra} — steadier tape, smaller gap.`);
  }
  if (VOL_NAK.has(naks)) {
    vol += 1.3;
    reasons.push(`${panchang.nakshatra} is a volatile nakshatra — expect a fast first 15 minutes.`);
  }

  const moon = planetByName(planets, "Moon");
  const sun = planetByName(planets, "Sun");
  const mars = planetByName(planets, "Mars");
  const jup = planetByName(planets, "Jupiter");
  const sat = planetByName(planets, "Saturn");
  const rahu = planetByName(planets, "Rahu");
  const ven = planetByName(planets, "Venus");
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
  if (yogas.some((y) => y.startsWith("Gajakesari"))) dir += 0.8;
  if (yogas.some((y) => y.startsWith("Kemadruma"))) vol += 0.5;
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

  dir += elementDir(moon.signIndex) * 0.8;
  dir += elementDir(signIndexOf(lagna)) * 0.7;

  const marsMoon = angularSep(mars.sidereal, moon.sidereal);
  if (marsMoon < 12 || Math.abs(marsMoon - 180) < 10) {
    vol += 1.6;
    dir += marsMoon < 12 ? 0.4 : -0.3;
    reasons.push(`Mars ${marsMoon < 12 ? "conjunct" : "opposite"} Moon — opening impulse will be sharp.`);
  }

  const lagnaSign = signIndexOf(lagna);
  if (isKendra(lagnaSign, jup.signIndex) || isKendra(lagnaSign, ven.signIndex)) {
    dir += 1.5;
    reasons.push("Jupiter/Venus occupy a kendra from the 09:15 lagna — bid-to-cover open.");
  }
  if (isKendra(lagnaSign, sat.signIndex) || isKendra(lagnaSign, rahu.signIndex)) {
    dir -= 1.6;
    vol += 0.6;
    reasons.push("Saturn/Rahu on a kendra from the open lagna — supply at the bell.");
  }

  if (mer.retrograde) {
    vol += 1.1;
    dir *= 0.7;
    reasons.push("Mercury retrograde — gap often fades inside the first hour.");
  }
  if (angularSep(mer.sidereal, sun.sidereal) < 8.5) {
    vol += 0.8;
    reasons.push("Mercury combust — mixed tape, fade the first spike.");
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
  }

  reasons.push(
    `Open lagna is ${panchang.lagnaSign} ${panchang.lagnaDegree.toFixed(1)}° — ${elementDir(lagnaSign) > 0.5 ? "fire/air, expansion" : elementDir(lagnaSign) < 0 ? "water, absorption" : "earth, digestion"}.`,
  );

  const uniq: string[] = [];
  for (const r of reasons) {
    if (!uniq.includes(r)) uniq.push(r);
  }
  return { dir, vol, reasons: uniq.slice(0, 8) };
}

function volLabel(vol: number): GapCall["volatility"] {
  if (vol >= 4.2) return "extreme";
  if (vol >= 3.0) return "high";
  if (vol >= 1.8) return "medium";
  return "low";
}

function gapFromDir(dir: number, vol: number): GapCall["kind"] {
  const threshold = vol >= 3.2 ? 1.15 : 1.7;
  if (dir >= threshold) return "up";
  if (dir <= -threshold) return "down";
  return "flat";
}

function openAction(kind: GapCall["kind"], vol: GapCall["volatility"]): TradeAction {
  if (vol === "extreme") return "WAIT";
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
): GapCall {
  const { dir, vol, reasons } = scoreGap(panchang, planets, lagna);
  const kind = gapFromDir(dir, vol);
  const volatility = volLabel(vol);
  const confidence = clamp(Math.round(42 + Math.abs(dir) * 12 + (vol > 2 ? 6 : 0)), 52, 94);
  const bias: GapCall["bias"] = dir > 0.7 ? "bullish" : dir < -0.7 ? "bearish" : "neutral";
  const label = kind === "up" ? "GAP UP" : kind === "down" ? "GAP DOWN" : "FLAT / INSIDE";
  const action = openAction(kind, volatility);
  const ecl = eclipseCorridor(planets);
  const moon = planetByName(planets, "Moon");
  const yogas = specialYogas(panchang, planets, lagna);
  const firstHourNote =
    volatility === "extreme" || volatility === "high"
      ? `Do not chase 09:15. Let the first 15-minute candle close, then take ${horaLord} hora's side.`
      : kind === "flat"
        ? "Open inside yesterday — sell the wings, fade the first spike back to VWAP."
        : kind === "up"
          ? `Gap-up in ${horaLord} hora: buy CE only on a hold above the opening 5-minute low. PE only if it fails in 15 minutes.`
          : `Gap-down in ${horaLord} hora: buy PE on a hold below the opening 5-minute high. CE only if it reclaims immediately.`;

  const summary =
    kind === "up"
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
    gandanta: isGandanta(moon.sidereal) || isGandanta(lagna),
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
): { action: TradeAction; side: TradeSide; suggestion: string } {
  if (kalam.rahu) {
    return {
      action: "AVOID",
      side: "WAIT",
      suggestion: "Rahu Kalam — no fresh entries. If in profit, trail. If flat, sit on hands.",
    };
  }
  if (kalam.yamagandam && (regime.includes("Sideways") || regime.includes("Volatile"))) {
    return {
      action: "WAIT",
      side: "WAIT",
      suggestion: "Yamagandam overlapping a messy hora — skip this slot, reload next.",
    };
  }

  switch (regime) {
    case "Strong Positive":
      return { action: "BUY CE", side: "CE", suggestion: `Ride ${hora} hora. Buy ATM/ITM CE, trail. Do not average PE.` };
    case "Positive":
      return { action: "BUY CE", side: "CE", suggestion: "Buy CE on any 5-min dip. Book 40–50% at 1:1, trail the rest." };
    case "Volatile Positive":
      return { action: "SCALP CE", side: "CE", suggestion: "Fast CE scalps only. Tight stop under the prior 5-min low. No overnight." };
    case "Sideways to Positive":
      return { action: "SCALP CE", side: "CE", suggestion: "Range with a green tilt. Small CE, or a bull call debit spread." };
    case "Sideways/Volatile":
      return { action: "STRADDLE", side: "BOTH", suggestion: "Both sides live. Prefer a long straddle/strangle, or stay out if you only play direction." };
    case "Sideways to Negative":
      return { action: "SCALP PE", side: "PE", suggestion: "Range with a red tilt. Small PE, or a bear put debit spread." };
    case "Volatile Negative":
      return { action: "SCALP PE", side: "PE", suggestion: "Fast PE scalps. Tight stop above the prior 5-min high. Don't fade with CE." };
    case "Negative":
      return { action: "BUY PE", side: "PE", suggestion: "Buy PE on any 5-min pop. Book 40–50% at 1:1, trail the rest." };
    case "Strong Negative":
      return { action: "BUY PE", side: "PE", suggestion: `Ride ${hora} hora. Buy ATM/ITM PE, trail. Do not average CE.` };
  }
}

function productFor(underlying: Underlying, side: TradeSide, vol: number): string {
  const meta = UNDERLYINGS.find((u) => u.id === underlying)!;
  if (side === "WAIT") return "No contract";
  if (side === "BOTH") return `${underlying} ATM straddle · ${meta.step} pt wings`;
  const otm = vol >= 2.6 ? meta.step * 2 : vol >= 1.6 ? meta.step : 0;
  const which = side === "CE" ? "CE" : "PE";
  if (otm === 0) return `${underlying} ATM ${which}`;
  return `${underlying} ${otm} pts OTM ${which}`;
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
  planets: PlanetPos[],
  lagna: number,
  kalam: KalamFlag,
  cho: { kind: "good" | "move" | "bad" },
  abhijit: boolean,
): { dir: number; vol: number } {
  const hs = planetScore(hora);
  let dir = hs.dir;
  let vol = hs.vol + 0.4;
  dir += elementDir(signIndexOf(lagna)) * 0.55;
  dir += panchang.paksha === "Shukla" ? 0.35 : -0.35;
  if (FIERY_NAK.has(panchang.nakshatraIndex)) vol += 0.5;
  if (VOL_NAK.has(panchang.nakshatraIndex)) vol += 0.7;
  if (STABLE_NAK.has(panchang.nakshatraIndex)) vol -= 0.25;

  const jup = planetByName(planets, "Jupiter");
  const sat = planetByName(planets, "Saturn");
  const mars = planetByName(planets, "Mars");
  if (BULLISH.includes(hora) && isKendra(signIndexOf(lagna), jup.signIndex)) dir += 0.7;
  if (BEARISH.includes(hora) && isKendra(signIndexOf(lagna), sat.signIndex)) dir -= 0.7;
  if (hora === "Mars" || angularSep(mars.sidereal, lagna) < 8) vol += 0.6;
  if (CHOPPY.includes(hora)) vol += 0.5;
  if (kalam.rahu) {
    vol += 1.2;
    dir *= 0.35;
  }
  if (kalam.yamagandam) {
    vol += 0.6;
    dir *= 0.6;
  }
  if (kalam.gulika) dir -= 0.25;
  if (cho.kind === "good") dir += 0.45;
  if (cho.kind === "move") vol += 0.55;
  if (cho.kind === "bad") {
    dir *= 0.7;
    vol += 0.35;
  }
  if (abhijit) dir += 0.35;
  return { dir, vol };
}

function mergeNet(slots: WindowSlot[]): WindowSlot[] {
  if (!slots.length) return [];
  const out: WindowSlot[] = [];
  for (const s of slots) {
    const prev = out[out.length - 1];
    if (prev && prev.regime === s.regime && prev.action === s.action && prev.hora === s.hora) {
      prev.to = s.to;
      prev.toMin = s.toMin;
      prev.isLive = prev.isLive || s.isLive;
      prev.isPast = prev.isPast && s.isPast;
      prev.strength = Math.round((prev.strength + s.strength) / 2);
      continue;
    }
    out.push({ ...s, kalam: { ...s.kalam } });
  }
  return out;
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
  const gap = buildGap(panchang, planets, lagna, underlying, horaOpen.lord);
  const iso = formatIstIsoDate(open);
  const nowParts = getIstParts(now);
  const nowMin = minutesOfDay(nowParts.hour, nowParts.minute);
  const sameDay = nowParts.year === p.year && nowParts.month === p.month && nowParts.day === p.day;

  const raw: WindowSlot[] = SLOT_STARTS.map(([h, m], i) => {
    const fromMin = minutesOfDay(h, m);
    const next = SLOT_STARTS[i + 1];
    const toMin = next ? minutesOfDay(next[0], next[1]) : MARKET_CLOSE_MIN;
    const midMin = Math.floor((fromMin + toMin) / 2);
    const mid = utcFromIstParts(p.year, p.month, p.day, Math.floor(midMin / 60), midMin % 60, 0);
    const { panchang: pan, planets: pls, lagna: lag } = panchangAt(mid);
    const hora = horaAt(mid, pan);
    const kalam = kalamAt(mid, pan);
    const cho = choghadiyaAt(mid, pan);
    const abhijit = isAbhijit(mid, pan);
    const scored = scoreWindow(hora.lord, pan, pls, lag, kalam, cho, abhijit);
    const regime = regimeFrom(scored.dir, scored.vol);
    const traded = actionFrom(regime, kalam, hora.lord);
    const isLive = sameDay && nowMin >= fromMin && nowMin < toMin;
    const isPast = sameDay ? nowMin >= toMin : now.getTime() > mid.getTime();
    const strength = clamp(Math.round(36 + Math.abs(scored.dir) * 14 + scored.vol * 6), 40, 98);
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
      product: productFor(underlying, traded.side, scored.vol),
      suggestion: traded.suggestion,
      strength,
      confidence: clamp(Math.round(50 + Math.abs(scored.dir) * 10), 48, 92),
      kalam,
      why: slotWhy(hora.lord, signName(lag), kalam, regime, pan.nakshatra, cho.name, abhijit),
      isLive,
      isPast,
      choghadiya: cho.name,
      choghadiyaKind: cho.kind,
      abhijit,
    };
  });

  const slots = applyHoldBook(raw);

  const ceSlots = slots.filter((s) => s.side === "CE" && s.action !== "AVOID" && s.action !== "WAIT");
  const peSlots = slots.filter((s) => s.side === "PE" && s.action !== "AVOID" && s.action !== "WAIT");
  const bestCe = [...ceSlots].sort((a, b) => b.strength - a.strength)[0] ?? null;
  const bestPe = [...peSlots].sort((a, b) => b.strength - a.strength)[0] ?? null;
  const avoid = slots.filter((s) => s.action === "AVOID" || s.kalam.rahu);
  const last = slots[slots.length - 1];

  const headline = `${gap.label} · ${gap.volatility} vol · ${horaOpen.lord} hora at the bell · first trade ${gap.openAction}. Best CE ${bestCe ? `${bestCe.from}–${bestCe.to}` : "none"}. Best PE ${bestPe ? `${bestPe.from}–${bestPe.to}` : "none"}.`;

  const playbook: DayPlaybook = {
    date: iso,
    weekday: panchang.weekday,
    underlying,
    gap,
    panchang,
    bestCe,
    bestPe,
    avoid,
    closeBias: last.regime,
    headline,
    horaAtOpen: horaOpen.lord,
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
    netResults: mergeNet(slots),
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
