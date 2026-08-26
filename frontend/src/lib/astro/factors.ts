/**
 * Vedic market factors layered on the ephemeris: dignity, aspects, choghadiya,
 * gandanta, eclipse corridor, mundane India/NSE transits. Purely astrological.
 */

import {
  NAKSHATRAS,
  type AspectHit,
  type AspectKind,
  type DayThesis,
  type DignityHit,
  type DignityKind,
  type PlanetName,
  type PlanetPos,
  type Panchang,
  type Underlying,
} from "./types";
import { angularSep, isKendra, isTrikona, moonTropical, planetByName, snapshot } from "./ephemeris";
import { julianDate, utcFromIstParts } from "./time";

export type ChoghadiyaName = "Udveg" | "Chal" | "Labh" | "Amrit" | "Kaal" | "Shubh" | "Rog";
export type ChoghadiyaKind = "good" | "move" | "bad";

export interface ChoghadiyaInfo {
  name: ChoghadiyaName;
  kind: ChoghadiyaKind;
  index: number;
}

const EXALT: Record<PlanetName, { sign: number; degree: number }> = {
  Sun: { sign: 0, degree: 10 },
  Moon: { sign: 1, degree: 3 },
  Mars: { sign: 9, degree: 28 },
  Mercury: { sign: 5, degree: 15 },
  Jupiter: { sign: 3, degree: 5 },
  Venus: { sign: 11, degree: 27 },
  Saturn: { sign: 6, degree: 20 },
  Rahu: { sign: 1, degree: 20 },
  Ketu: { sign: 7, degree: 20 },
};

const OWN: Record<PlanetName, number[]> = {
  Sun: [4],
  Moon: [3],
  Mars: [0, 7],
  Mercury: [2, 5],
  Jupiter: [8, 11],
  Venus: [1, 6],
  Saturn: [9, 10],
  Rahu: [10],
  Ketu: [7],
};

const MOOLA: Record<PlanetName, number> = {
  Sun: 4,
  Moon: 3,
  Mars: 0,
  Mercury: 5,
  Jupiter: 8,
  Venus: 6,
  Saturn: 10,
  Rahu: 10,
  Ketu: 7,
};

const CHO_CYCLE: ChoghadiyaName[] = ["Udveg", "Chal", "Labh", "Amrit", "Kaal", "Shubh", "Rog"];
const DAY_START: ChoghadiyaName[] = ["Udveg", "Amrit", "Rog", "Labh", "Shubh", "Chal", "Kaal"];

export function dignityOf(p: PlanetPos): DignityHit {
  const exalt = EXALT[p.name];
  const own = OWN[p.name] ?? [];
  let dignity: DignityKind = "neutral";
  if (exalt && p.signIndex === exalt.sign) dignity = "exalted";
  else if (exalt && p.signIndex === (exalt.sign + 6) % 12) dignity = "debilitated";
  else if (MOOLA[p.name] === p.signIndex && own.includes(p.signIndex)) dignity = "moolatrikona";
  else if (own.includes(p.signIndex)) dignity = "own";
  const label =
    dignity === "exalted"
      ? `${p.name} exalted in ${p.sign}`
      : dignity === "debilitated"
        ? `${p.name} debilitated in ${p.sign}`
        : dignity === "own" || dignity === "moolatrikona"
          ? `${p.name} in own ${p.sign}`
          : `${p.name} in ${p.sign}`;
  return { name: p.name, dignity, label };
}

function westernAspect(sep: number): { kind: AspectKind; orb: number } | null {
  const targets: [AspectKind, number, number][] = [
    ["conjunction", 0, 8],
    ["sextile", 60, 4],
    ["square", 90, 6],
    ["trine", 120, 6],
    ["opposition", 180, 8],
  ];
  for (const [kind, exact, max] of targets) {
    const orb = Math.abs(sep - exact);
    if (orb <= max) return { kind, orb };
  }
  return null;
}

const ASPECT_NOTE: Record<AspectKind, string> = {
  conjunction: "fused — one tape, sharp open",
  opposition: "polarity — gap-and-fade or two-way",
  square: "friction — whip, not a clean trend",
  trine: "flow — the move can run",
  sextile: "opportunity — constructive if hora agrees",
};

export function findAspects(planets: PlanetPos[]): AspectHit[] {
  const names: PlanetName[] = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu"];
  const hits: AspectHit[] = [];
  for (let i = 0; i < names.length; i++) {
    for (let j = i + 1; j < names.length; j++) {
      const a = planetByName(planets, names[i]);
      const b = planetByName(planets, names[j]);
      const sep = angularSep(a.sidereal, b.sidereal);
      const hit = westernAspect(sep);
      if (!hit) continue;
      hits.push({
        a: a.name,
        b: b.name,
        kind: hit.kind,
        orb: Math.round(hit.orb * 10) / 10,
        note: `${a.name} ${hit.kind} ${b.name} (${hit.orb.toFixed(1)}°) — ${ASPECT_NOTE[hit.kind]}`,
      });
    }
  }
  hits.sort((x, y) => x.orb - y.orb);
  return hits.slice(0, 10);
}

export function isGandanta(sidereal: number): boolean {
  const d = ((sidereal % 360) + 360) % 360;
  const inSign = d % 30;
  const sign = Math.floor(d / 30) % 12;
  const water = sign === 3 || sign === 7 || sign === 11;
  const fire = sign === 0 || sign === 4 || sign === 8;
  if (water && inSign >= 29) return true;
  if (fire && inSign <= 1) return true;
  return false;
}

export function eclipseCorridor(planets: PlanetPos[]): { active: boolean; note: string | null } {
  const sun = planetByName(planets, "Sun");
  const moon = planetByName(planets, "Moon");
  const rahu = planetByName(planets, "Rahu");
  const sunNode = angularSep(sun.sidereal, rahu.sidereal);
  const moonNode = angularSep(moon.sidereal, rahu.sidereal);
  const moonOpp = angularSep(moon.sidereal, (rahu.sidereal + 180) % 360);
  const syzygy = angularSep(sun.sidereal, moon.sidereal);
  const nearNode = sunNode < 18 || Math.abs(sunNode - 180) < 18;
  const lunation = syzygy < 12 || Math.abs(syzygy - 180) < 12;
  if (nearNode && lunation) {
    return {
      active: true,
      note: `Eclipse corridor — Sun/Moon within 18° of the nodes. Expect a fake first hour.`,
    };
  }
  if (moonNode < 8 || moonOpp < 8) {
    return { active: true, note: "Moon on the nodal axis — headline gap, fade the first spike." };
  }
  return { active: false, note: null };
}

export function moonSpeedDegPerDay(date: Date): number {
  const jd = julianDate(date);
  const a = moonTropical(jd);
  const b = moonTropical(jd + 1);
  let d = b - a;
  if (d < 0) d += 360;
  if (d > 180) d -= 360;
  return Math.abs(d);
}

export function choghadiyaAt(date: Date, panchang: Panchang): ChoghadiyaInfo {
  const rise = new Date(panchang.sunriseIso).getTime();
  const set = new Date(panchang.sunsetIso).getTime();
  const part = (set - rise) / 8;
  const elapsed = date.getTime() - rise;
  const idx = elapsed < 0 ? 0 : Math.min(7, Math.floor(elapsed / Math.max(1, part)));
  const startName = DAY_START[panchang.weekdayIndex];
  const start = CHO_CYCLE.indexOf(startName);
  const name = CHO_CYCLE[(start + idx) % 7];
  const kind: ChoghadiyaKind = name === "Amrit" || name === "Shubh" || name === "Labh" ? "good" : name === "Chal" ? "move" : "bad";
  return { name, kind, index: idx };
}

export function isAbhijit(date: Date, panchang: Panchang): boolean {
  const rise = new Date(panchang.sunriseIso).getTime();
  const set = new Date(panchang.sunsetIso).getTime();
  const mid = (rise + set) / 2;
  const half = 12 * 60 * 1000;
  const t = date.getTime();
  return t >= mid - half && t <= mid + half;
}

export function specialYogas(panchang: Panchang, planets: PlanetPos[], lagna: number): string[] {
  const out: string[] = [];
  const moon = planetByName(planets, "Moon");
  const jup = planetByName(planets, "Jupiter");
  const mars = planetByName(planets, "Mars");
  const sat = planetByName(planets, "Saturn");
  const mer = planetByName(planets, "Mercury");
  const sun = planetByName(planets, "Sun");
  const ven = planetByName(planets, "Venus");
  const rahu = planetByName(planets, "Rahu");
  const lagnaSign = Math.floor((((lagna % 360) + 360) % 360) / 30) % 12;

  if (isKendra(moon.signIndex, jup.signIndex) || isTrikona(moon.signIndex, jup.signIndex)) {
    out.push("Gajakesari — Moon/Jupiter in kendra or trikona. Bid-to-cover days.");
  }
  const neighbours = [(moon.signIndex + 11) % 12, (moon.signIndex + 1) % 12];
  const occupied = new Set(planets.filter((p) => p.name !== "Moon" && p.name !== "Rahu" && p.name !== "Ketu").map((p) => p.signIndex));
  if (!neighbours.some((s) => occupied.has(s))) {
    out.push("Kemadruma — empty 2nd/12th from Moon. Isolated tape, fade extremes.");
  }
  if (mars.signIndex === jup.signIndex || isKendra(mars.signIndex, jup.signIndex)) {
    out.push("Guru-Mangala — Jupiter/Mars linked. Fast directional impulse.");
  }
  if (angularSep(mer.sidereal, sun.sidereal) < 12 && mer.signIndex === sun.signIndex) {
    out.push("Budha-Aditya — Mercury with Sun. News-driven, choppy open.");
  }
  if (angularSep(ven.sidereal, moon.sidereal) < 10) {
    out.push("Chandra-Shukra — liquidity, mean-reversion works.");
  }
  if (angularSep(mars.sidereal, rahu.sidereal) < 10) {
    out.push("Mangal-Rahu — shock window. Size down, no averaging.");
  }
  if (angularSep(sat.sidereal, rahu.sidereal) < 10) {
    out.push("Shani-Rahu — heavy supply. PE is the default until hora flips.");
  }
  if (isKendra(lagnaSign, jup.signIndex) && dignityOf(jup).dignity !== "debilitated") {
    out.push("Lagna-Guru kendra — constructive first hour if hora agrees.");
  }
  if (panchang.nakshatra === "Pushya" || panchang.nakshatra === "Rohini" || panchang.nakshatra === "Hasta") {
    out.push(`${panchang.nakshatra} Moon — classic wealth nakshatra, cleaner CE days.`);
  }
  if (panchang.nakshatra === "Ardra" || panchang.nakshatra === "Ashlesha" || panchang.nakshatra === "Jyeshtha" || panchang.nakshatra === "Mula") {
    out.push(`${panchang.nakshatra} Moon — sharp, often a trap-open.`);
  }
  return out.slice(0, 6);
}

let indiaNatal: PlanetPos[] | null = null;
let nseNatal: PlanetPos[] | null = null;

function natalIndia(): PlanetPos[] {
  if (!indiaNatal) indiaNatal = snapshot(utcFromIstParts(1947, 8, 15, 0, 0, 0)).planets;
  return indiaNatal;
}

function natalNse(): PlanetPos[] {
  if (!nseNatal) nseNatal = snapshot(utcFromIstParts(1994, 11, 3, 10, 0, 0)).planets;
  return nseNatal;
}

export function mundaneHits(planets: PlanetPos[]): string[] {
  const notes: string[] = [];
  const mars = planetByName(planets, "Mars");
  const sat = planetByName(planets, "Saturn");
  const jup = planetByName(planets, "Jupiter");
  const rahu = planetByName(planets, "Rahu");
  const indiaMoon = planetByName(natalIndia(), "Moon");
  const indiaSun = planetByName(natalIndia(), "Sun");
  const nseMoon = planetByName(natalNse(), "Moon");

  if (angularSep(mars.sidereal, indiaMoon.sidereal) < 3) {
    notes.push("Mars on India's natal Moon — historically a shock session.");
  }
  if (angularSep(sat.sidereal, indiaMoon.sidereal) < 3) {
    notes.push("Saturn on India's natal Moon — heavy, slow grind lower.");
  }
  if (angularSep(jup.sidereal, indiaMoon.sidereal) < 3) {
    notes.push("Jupiter on India's natal Moon — sponsorship of the bid.");
  }
  if (angularSep(rahu.sidereal, indiaSun.sidereal) < 4) {
    notes.push("Rahu on India's natal Sun — headline gap, don't trust the first print.");
  }
  if (angularSep(mars.sidereal, nseMoon.sidereal) < 3 || angularSep(sat.sidereal, nseMoon.sidereal) < 3) {
    notes.push("Malefic on NSE's natal Moon — index-specific pressure.");
  }
  if (angularSep(jup.sidereal, nseMoon.sidereal) < 3) {
    notes.push("Jupiter on NSE natal Moon — constructive for the cash tape.");
  }
  return notes;
}

export function aspectScore(hits: AspectHit[]): { dir: number; vol: number; reasons: string[] } {
  let dir = 0;
  let vol = 0;
  const reasons: string[] = [];
  for (const h of hits) {
    const pair = `${h.a}-${h.b}`;
    const hot = pair.includes("Mars") || pair.includes("Rahu") || pair.includes("Ketu");
    const heavy = pair.includes("Saturn");
    const soft = pair.includes("Jupiter") || pair.includes("Venus");
    if (h.kind === "conjunction" || h.kind === "opposition") {
      vol += hot ? 1.1 : 0.45;
      if (soft) dir += 0.55;
      if (heavy) dir -= 0.7;
      if (hot) dir += pair.includes("Mars") && !heavy ? 0.25 : -0.2;
    } else if (h.kind === "square") {
      vol += 0.8;
      dir -= 0.15;
    } else if (h.kind === "trine") {
      dir += soft || pair.includes("Moon") ? 0.55 : 0.2;
      vol -= 0.15;
    }
    if (reasons.length < 3 && h.orb <= 4) reasons.push(h.note);
  }
  return { dir, vol, reasons };
}

export function dignityScore(planets: PlanetPos[]): { dir: number; vol: number; reasons: string[] } {
  let dir = 0;
  let vol = 0;
  const reasons: string[] = [];
  for (const p of planets) {
    if (p.name === "Rahu" || p.name === "Ketu") continue;
    const d = dignityOf(p);
    if (d.dignity === "exalted") {
      dir += p.name === "Saturn" ? -0.4 : 0.7;
      reasons.push(d.label);
    } else if (d.dignity === "debilitated") {
      dir += p.name === "Saturn" ? 0.35 : -0.55;
      vol += 0.35;
      reasons.push(d.label);
    } else if (d.dignity === "own" || d.dignity === "moolatrikona") {
      dir += p.name === "Saturn" ? -0.2 : 0.25;
    }
    if (p.retrograde && (p.name === "Mercury" || p.name === "Venus" || p.name === "Mars")) {
      vol += 0.45;
      reasons.push(`${p.name} retrograde — first move often fails.`);
    }
  }
  return { dir, vol, reasons: reasons.slice(0, 4) };
}

export function nakshatraLabel(sidereal: number): string {
  const i = Math.floor((((sidereal % 360) + 360) % 360) / (360 / 27)) % 27;
  return NAKSHATRAS[i];
}

/** Mundane sector lords: who "owns" each cash index. */
export const SECTOR_LORDS: Record<Underlying, PlanetName[]> = {
  NIFTY: ["Mercury", "Sun"],
  BANKNIFTY: ["Jupiter", "Venus"],
  FINNIFTY: ["Jupiter", "Mercury"],
  SENSEX: ["Sun", "Saturn"],
  MIDCPNIFTY: ["Mars", "Mercury"],
};

/**
 * Hora is a colour, not a new thesis. These weights are small on purpose —
 * a Jupiter hora on a fade-bearish day is a bounce, not BUY CE.
 */
export function horaModulation(hora: PlanetName): { dir: number; vol: number } {
  switch (hora) {
    case "Jupiter":
      return { dir: 0.85, vol: 0.25 };
    case "Venus":
      return { dir: 0.55, vol: 0.3 };
    case "Sun":
      return { dir: 0.65, vol: 0.45 };
    case "Mars":
      return { dir: 0.35, vol: 1.1 };
    case "Mercury":
      return { dir: 0.05, vol: 0.85 };
    case "Moon":
      return { dir: 0.1, vol: 0.75 };
    case "Saturn":
      return { dir: -0.9, vol: 0.4 };
    case "Rahu":
      return { dir: -0.35, vol: 1.2 };
    case "Ketu":
      return { dir: -0.5, vol: 0.9 };
  }
}

/** Parashara graha drishti counted in signs from occupation (1st = occupied). */
export function drishtiSigns(fromSign: number, planet: PlanetName): number[] {
  const out = new Set<number>([(fromSign + 6) % 12]);
  if (planet === "Mars") {
    out.add((fromSign + 3) % 12);
    out.add((fromSign + 7) % 12);
  }
  if (planet === "Jupiter" || planet === "Rahu" || planet === "Ketu") {
    out.add((fromSign + 4) % 12);
    out.add((fromSign + 8) % 12);
  }
  if (planet === "Saturn") {
    out.add((fromSign + 2) % 12);
    out.add((fromSign + 9) % 12);
  }
  return [...out];
}

export function lagnaState(
  planets: PlanetPos[],
  lagna: number,
): {
  occupiedBy: PlanetName[];
  aspectedBy: PlanetName[];
  maleficOnLagna: boolean;
  note: string | null;
} {
  const lagnaSign = Math.floor((((lagna % 360) + 360) % 360) / 30) % 12;
  const occupiedBy = planets.filter((p) => p.signIndex === lagnaSign).map((p) => p.name);
  const aspectedBy: PlanetName[] = [];
  for (const p of planets) {
    if (p.signIndex === lagnaSign) continue;
    if (drishtiSigns(p.signIndex, p.name).includes(lagnaSign)) aspectedBy.push(p.name);
  }
  const malefics = new Set<PlanetName>(["Saturn", "Mars", "Rahu", "Ketu"]);
  const maleficOnLagna = occupiedBy.some((n) => malefics.has(n));
  let note: string | null = null;
  if (occupiedBy.includes("Saturn")) {
    note = "Saturn occupies the open lagna — the body of the tape is heavy. First print is supply.";
  } else if (occupiedBy.includes("Rahu") || occupiedBy.includes("Ketu")) {
    note = "Node on the open lagna — illusion at the bell. Fade the first spike.";
  } else if (occupiedBy.includes("Mars")) {
    note = "Mars on the open lagna — sharp open, two-way first 15 minutes.";
  } else if (aspectedBy.includes("Saturn") && aspectedBy.includes("Jupiter")) {
    note = "Saturn and Jupiter both aspect lagna — digestion, not a clean trend.";
  } else if (aspectedBy.includes("Jupiter")) {
    note = "Jupiter aspects the open lagna — a bid can appear if the sector lord agrees.";
  }
  return { occupiedBy, aspectedBy, maleficOnLagna, note };
}

export function nodalAffliction(planets: PlanetPos[], names: PlanetName[]): boolean {
  const rahu = planetByName(planets, "Rahu");
  for (const n of names) {
    const p = planetByName(planets, n);
    const sep = angularSep(p.sidereal, rahu.sidereal);
    if (sep < 8 || Math.abs(sep - 180) < 8 || Math.abs(sep - 90) < 6) return true;
    if (drishtiSigns(rahu.signIndex, "Rahu").includes(p.signIndex)) return true;
  }
  return false;
}

export function sectorScore(
  underlying: Underlying,
  planets: PlanetPos[],
  lagna: number,
): { dir: number; vol: number; note: string; afflicted: boolean } {
  const lords = SECTOR_LORDS[underlying];
  const lag = lagnaState(planets, lagna);
  let dir = 0;
  let vol = 0;
  let afflicted = false;
  const bits: string[] = [];
  for (const name of lords) {
    const p = planetByName(planets, name);
    const d = dignityOf(p);
    if (d.dignity === "exalted") {
      dir += name === "Saturn" ? -0.45 : 1.15;
      bits.push(`${name} exalted — sponsors ${underlying}`);
    } else if (d.dignity === "debilitated") {
      dir -= 0.7;
      vol += 0.3;
      bits.push(`${name} debilitated — ${underlying} liquidity is thin`);
    } else if (d.dignity === "own" || d.dignity === "moolatrikona") {
      dir += 0.35;
    }
    if (nodalAffliction(planets, [name])) {
      afflicted = true;
      dir -= 1.05;
      vol += 0.55;
      bits.push(`${name} under the nodes — ${underlying} first move is a trap`);
    }
    if (p.retrograde) {
      vol += 0.3;
      dir *= 0.88;
    }
    if (name === "Jupiter" && lag.aspectedBy.includes("Jupiter")) {
      dir += 0.95;
      bits.push(`Guru drishti on lagna — ${underlying} can hold even when the cash tape looks heavy`);
    }
  }
  const note = bits[0] ?? `${lords.join("/")} rule ${underlying}.`;
  return { dir, vol, note, afflicted };
}

export interface Thesis {
  kind: DayThesis;
  dir: number;
  vol: number;
  fadeOpen: boolean;
  note: string;
  sectorNote: string;
}

export function classifyThesis(args: {
  panchang: Panchang;
  planets: PlanetPos[];
  lagna: number;
  underlying: Underlying;
  baseDir: number;
  baseVol: number;
  yogas: string[];
  eclipse: boolean;
}): Thesis {
  const { panchang, planets, lagna, underlying, baseDir, baseVol, yogas, eclipse } = args;
  const t = panchang.tithiIndex % 15;
  const rikta = t === 3 || t === 8 || t === 13;
  const fullEmpty = panchang.tithiName === "Purnima" || panchang.tithiName === "Amavasya";
  const lag = lagnaState(planets, lagna);
  const sector = sectorScore(underlying, planets, lagna);
  const merSunNode = nodalAffliction(planets, ["Mercury", "Sun"]);
  const kemadruma = yogas.some((y) => y.startsWith("Kemadruma"));
  const budha = yogas.some((y) => y.startsWith("Budha-Aditya"));
  const marsSat = findAspects(planets).some(
    (h) =>
      ((h.a === "Mars" && h.b === "Saturn") || (h.a === "Saturn" && h.b === "Mars")) &&
      (h.kind === "square" || h.kind === "opposition"),
  );

  let fadeScore = 0;
  if (rikta) fadeScore += 2;
  if (sector.afflicted || merSunNode) fadeScore += 2;
  if (lag.maleficOnLagna) fadeScore += 1;
  if (kemadruma && budha) fadeScore += 1;
  if (eclipse) fadeScore += 2;
  if (fullEmpty) fadeScore += 1;

  let dir = baseDir + sector.dir;
  let vol = baseVol + sector.vol;
  if (lag.maleficOnLagna) dir -= 0.85;
  if (lag.note && lag.occupiedBy.includes("Saturn")) vol += 0.25;
  if (!eclipse) vol = Math.min(vol, 4.0);

  let kind: DayThesis;
  if (fadeScore >= 3) kind = "fade";
  else if (marsSat || (vol >= 3.6 && Math.abs(dir) < 1.0)) kind = "chop";
  else if (dir >= 0.9) kind = "trend-up";
  else if (dir <= -0.9) kind = "trend-down";
  else kind = "chop";

  const fadeOpen = kind === "fade" || kind === "chop" || rikta || eclipse;

  let note: string;
  if (kind === "fade") {
    note =
      sector.afflicted || merSunNode
        ? `Fade day for ${underlying}: the first hora is a trap. Sit 09:15, then trade the ${dir < 0 ? "malefic lagna (PE)" : "sector bid (CE)"}.`
        : `Rikta/unstable open. Don't chase the bell. Residual is ${dir < 0 ? "PE" : dir > 0 ? "CE" : "two-way"}.`;
  } else if (kind === "trend-up") {
    note = "Trend-up thesis. Benefic horas add CE; malefic horas book or hold — they do not flip the day to PE.";
  } else if (kind === "trend-down") {
    note = "Trend-down thesis. Malefic horas add PE; benefic horas scalp the bounce — they do not start a new CE trend.";
  } else {
    note = "Chop thesis. Straddle or sit. Direction is a coin-flip until hora and choghadiya agree.";
  }

  return { kind, dir, vol, fadeOpen, note, sectorNote: sector.note };
}

