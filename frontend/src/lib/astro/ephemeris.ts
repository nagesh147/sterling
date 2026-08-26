/**
 * Artifact A4 — sidereal (Lahiri) ephemeris.
 *
 * Sun/Moon: Meeus truncated series. Planets: JPL Keplerian elements (1800–2050).
 * Rahu: mean lunar node. Lagna: equatorial-to-ecliptic at Mumbai.
 * Accurate to ~0.3° Moon / ~1° planets — enough for nakshatra, tithi, hora, lagna rashi.
 */

import { SIGNS, type PlanetName, type PlanetPos } from "./types";
import { julianDate, MUMBAI } from "./time";

const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;

export function norm360(deg: number): number {
  const x = deg % 360;
  return x < 0 ? x + 360 : x;
}

export function sind(d: number): number {
  return Math.sin(d * D2R);
}
export function cosd(d: number): number {
  return Math.cos(d * D2R);
}

function centuries(jd: number): number {
  return (jd - 2451545.0) / 36525;
}

/** Chitrapaksha / Lahiri ayanamsa. J2000 = 23°51'11.26", 50.2388475"/yr. */
export function lahiriAyanamsa(jd: number): number {
  const years = (jd - 2451545.0) / 365.25;
  return 23.8531278 + (50.2388475 / 3600) * years;
}

export function signIndex(sidereal: number): number {
  return Math.floor(norm360(sidereal) / 30) % 12;
}

export function signName(sidereal: number): string {
  return SIGNS[signIndex(sidereal)];
}

export function degreeInSign(sidereal: number): number {
  return norm360(sidereal) % 30;
}

export function nakshatraIndex(siderealMoon: number): number {
  return Math.floor(norm360(siderealMoon) / (360 / 27)) % 27;
}

export function nakshatraPada(siderealMoon: number): number {
  const span = 360 / 27;
  const pos = norm360(siderealMoon) % span;
  return Math.min(4, Math.floor(pos / (span / 4)) + 1);
}

export function sunTropical(jd: number): number {
  const T = centuries(jd);
  const L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T;
  const M = 357.52911 + 35999.05029 * T - 0.0001537 * T * T;
  const C =
    (1.914602 - 0.004817 * T - 0.000014 * T * T) * sind(M) +
    (0.019993 - 0.000101 * T) * sind(2 * M) +
    0.000289 * sind(3 * M);
  return norm360(L0 + C);
}

export function moonTropical(jd: number): number {
  const T = centuries(jd);
  const Lp = 218.3164477 + 481267.88123421 * T - 0.0015786 * T * T + T * T * T / 538841 - T ** 4 / 65194000;
  const D = 297.8501921 + 445267.1114034 * T - 0.0018819 * T * T + T * T * T / 545868;
  const M = 357.5291092 + 35999.0502909 * T - 0.0001536 * T * T + T * T * T / 24490000;
  const Mp = 134.9633964 + 477198.8675055 * T + 0.0087414 * T * T + T * T * T / 69699;
  const F = 93.272095 + 483202.0175233 * T - 0.0036539 * T * T;
  const E = 1 - 0.002516 * T - 0.0000074 * T * T;

  const terms: [number, number, number, number, number][] = [
    [6288774, 0, 0, 1, 0],
    [1274027, 2, 0, -1, 0],
    [658314, 2, 0, 0, 0],
    [213618, 0, 0, 2, 0],
    [-185116, 0, 1, 0, 0],
    [-114332, 0, 0, 0, 2],
    [58793, 2, 0, -2, 0],
    [57066, 2, -1, -1, 0],
    [53322, 2, 0, 1, 0],
    [45758, 2, -1, 0, 0],
    [-40923, 0, 1, -1, 0],
    [-34720, 1, 0, 0, 0],
    [-30383, 0, 1, 1, 0],
    [15327, 2, 0, 0, -2],
    [-12528, 0, 0, 1, 2],
    [10980, 0, 0, 1, -2],
    [10675, 4, 0, -1, 0],
    [10034, 0, 0, 3, 0],
    [8548, 4, 0, -2, 0],
    [-7888, 2, 1, -1, 0],
    [-6766, 2, 1, 0, 0],
    [-5163, 1, 0, -1, 0],
    [4987, 1, 1, 0, 0],
    [4036, 2, -1, 1, 0],
    [3994, 2, 0, 2, 0],
    [3861, 4, 0, 0, 0],
    [3665, 2, 0, -3, 0],
    [-2689, 0, 1, -2, 0],
    [-2602, 2, 0, -1, 2],
    [2390, 2, -1, -2, 0],
  ];

  let sum = 0;
  for (const [coef, d, m, mp, f] of terms) {
    const arg = d * D + m * M + mp * Mp + f * F;
    const ePow = Math.abs(m) === 1 ? E : Math.abs(m) === 2 ? E * E : 1;
    sum += coef * ePow * sind(arg);
  }
  return norm360(Lp + sum / 1_000_000);
}

/** Mean lunar ascending node (always retrograde in the mean). */
export function rahuTropical(jd: number): number {
  const T = centuries(jd);
  return norm360(125.04452 - 1934.136261 * T + 0.0020708 * T * T + T * T * T / 450000);
}

type KeplerRow = {
  name: "Mercury" | "Venus" | "Earth" | "Mars" | "Jupiter" | "Saturn";
  a: number;
  aDot: number;
  e: number;
  eDot: number;
  I: number;
  IDot: number;
  L: number;
  LDot: number;
  wbar: number;
  wbarDot: number;
  Omega: number;
  OmegaDot: number;
};

const KEPLER: KeplerRow[] = [
  { name: "Mercury", a: 0.38709927, aDot: 0.00000037, e: 0.20563593, eDot: 0.00001906, I: 7.00497902, IDot: -0.00594749, L: 252.2503235, LDot: 149472.67411175, wbar: 77.45779628, wbarDot: 0.16047689, Omega: 48.33076593, OmegaDot: -0.12534081 },
  { name: "Venus", a: 0.72333566, aDot: 0.0000039, e: 0.00677672, eDot: -0.00004107, I: 3.39467605, IDot: -0.0007889, L: 181.9790995, LDot: 58517.81538729, wbar: 131.60246718, wbarDot: 0.00268329, Omega: 76.67984255, OmegaDot: -0.27769418 },
  { name: "Earth", a: 1.00000261, aDot: 0.00000562, e: 0.01671123, eDot: -0.00004392, I: -0.00001531, IDot: -0.01294668, L: 100.46457154, LDot: 35999.37244981, wbar: 102.93768193, wbarDot: 0.32327364, Omega: 0, OmegaDot: 0 },
  { name: "Mars", a: 1.52371034, aDot: 0.00001847, e: 0.0933941, eDot: 0.00007882, I: 1.84954123, IDot: -0.00813131, L: -4.55343205, LDot: 19140.30268499, wbar: -23.94362959, wbarDot: 0.44441088, Omega: 49.55953891, OmegaDot: -0.29257343 },
  { name: "Jupiter", a: 5.202887, aDot: -0.00011607, e: 0.04838624, eDot: -0.00013253, I: 1.30439695, IDot: -0.00183714, L: 34.39644051, LDot: 3034.74612775, wbar: 14.72847983, wbarDot: 0.21252668, Omega: 100.47390909, OmegaDot: 0.20469106 },
  { name: "Saturn", a: 9.53667594, aDot: -0.0012506, e: 0.05386179, eDot: -0.00050991, I: 2.48599187, IDot: 0.00193609, L: 49.95424423, LDot: 1222.49362201, wbar: 92.59887831, wbarDot: -0.41897216, Omega: 113.66242448, OmegaDot: -0.28867794 },
];

function keplerE(M: number, e: number): number {
  let E = M;
  for (let i = 0; i < 12; i++) {
    E = E - (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
  }
  return E;
}

function helioEcliptic(row: KeplerRow, T: number): { x: number; y: number; z: number } {
  const a = row.a + row.aDot * T;
  const e = row.e + row.eDot * T;
  const I = (row.I + row.IDot * T) * D2R;
  const L = (row.L + row.LDot * T) * D2R;
  const wbar = (row.wbar + row.wbarDot * T) * D2R;
  const Omega = (row.Omega + row.OmegaDot * T) * D2R;
  const w = wbar - Omega;
  let M = L - wbar;
  M = ((M + Math.PI) % (2 * Math.PI)) - Math.PI;
  const E = keplerE(M, e);
  const xv = a * (Math.cos(E) - e);
  const yv = a * Math.sqrt(1 - e * e) * Math.sin(E);
  const v = Math.atan2(yv, xv);
  const r = Math.hypot(xv, yv);
  const xh =
    r * (Math.cos(Omega) * Math.cos(v + w) - Math.sin(Omega) * Math.sin(v + w) * Math.cos(I));
  const yh =
    r * (Math.sin(Omega) * Math.cos(v + w) + Math.cos(Omega) * Math.sin(v + w) * Math.cos(I));
  const zh = r * Math.sin(v + w) * Math.sin(I);
  return { x: xh, y: yh, z: zh };
}

function geoLongitude(planet: { x: number; y: number; z: number }, earth: { x: number; y: number; z: number }): number {
  const x = planet.x - earth.x;
  const y = planet.y - earth.y;
  return norm360(Math.atan2(y, x) * R2D);
}

export function planetTropical(name: Exclude<PlanetName, "Sun" | "Moon" | "Rahu" | "Ketu">, jd: number): number {
  const T = centuries(jd);
  const earth = helioEcliptic(KEPLER[2], T);
  const row = KEPLER.find((r) => r.name === name);
  if (!row) return 0;
  return geoLongitude(helioEcliptic(row, T), earth);
}

export function obliquity(jd: number): number {
  const T = centuries(jd);
  return 23.439291 - 0.0130042 * T - 1.64e-7 * T * T + 5.04e-7 * T * T * T;
}

export function gmstHours(jd: number): number {
  const T = centuries(jd);
  const gmst = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * T * T - T * T * T / 38710000;
  return norm360(gmst) / 15;
}

/** Tropical ascendant at geographic lat/lon (east positive). */
export function tropicalAscendant(jd: number, lat = MUMBAI.lat, lon = MUMBAI.lon): number {
  const gast = gmstHours(jd);
  const lstHours = gast + lon / 15;
  const ramc = norm360(lstHours * 15) * D2R;
  const e = obliquity(jd) * D2R;
  const phi = lat * D2R;
  const y = -Math.cos(ramc);
  const x = Math.sin(ramc) * Math.cos(e) + Math.tan(phi) * Math.sin(e);
  let asc = Math.atan2(y, x) * R2D;
  if (asc < 0) asc += 360;
  return norm360(asc);
}

export function solarDeclination(jd: number): number {
  const L = sunTropical(jd) * D2R;
  const e = obliquity(jd) * D2R;
  return Math.asin(Math.sin(e) * Math.sin(L));
}

/** Sunrise / sunset Julian dates at Mumbai (civil -0.83°). */
export function sunRiseSet(jdNoon: number, lat = MUMBAI.lat, lon = MUMBAI.lon): { rise: number; set: number } {
  const n = Math.floor(jdNoon - 2451545 + 0.0008);
  const Jstar = n - lon / 360;
  const M = norm360(357.5291 + 0.98560028 * Jstar);
  const C = 1.9148 * sind(M) + 0.02 * sind(2 * M) + 0.0003 * sind(3 * M);
  const lam = norm360(M + C + 180 + 102.9372);
  const Jtransit = 2451545.0 + Jstar + 0.0053 * sind(M) - 0.0069 * sind(2 * lam);
  const decl = Math.asin(sind(lam) * sind(23.4397));
  const latR = lat * D2R;
  const cosH = (sind(-0.83) - Math.sin(latR) * Math.sin(decl)) / (Math.cos(latR) * Math.cos(decl));
  const H = Math.acos(Math.min(1, Math.max(-1, cosH)));
  return { rise: Jtransit - H / (2 * Math.PI), set: Jtransit + H / (2 * Math.PI) };
}

/** Sunrise/set for an IST civil date (year, month 1-12, day).
 *  Use UTC noon of that civil date — IST local noon (06:30 UTC) floors onto the previous NOAA day. */
export function sunRiseSetIst(year: number, month: number, day: number, lat = MUMBAI.lat, lon = MUMBAI.lon): { rise: number; set: number } {
  const utcNoon = Date.UTC(year, month - 1, day, 12, 0, 0);
  return sunRiseSet(julianDate(new Date(utcNoon)), lat, lon);
}


function makePlanet(name: PlanetName, tropical: number, ayan: number, retrograde: boolean): PlanetPos {
  const sidereal = norm360(tropical - ayan);
  return {
    name,
    tropical: norm360(tropical),
    sidereal,
    sign: signName(sidereal),
    signIndex: signIndex(sidereal),
    degreeInSign: degreeInSign(sidereal),
    retrograde,
  };
}

export function snapshot(date: Date): { jd: number; ayan: number; planets: PlanetPos[]; lagnaSidereal: number } {
  const jd = julianDate(date);
  const ayan = lahiriAyanamsa(jd);
  const jd2 = jd + 1 / 24; // one hour later for motion sign
  const sun = sunTropical(jd);
  const moon = moonTropical(jd);
  const rahu = rahuTropical(jd);
  const names: Exclude<PlanetName, "Sun" | "Moon" | "Rahu" | "Ketu">[] = [
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
  ];
  const planets: PlanetPos[] = [
    makePlanet("Sun", sun, ayan, false),
    makePlanet("Moon", moon, ayan, moonTropical(jd2) < moon && moon - moonTropical(jd2) < 180 ? false : false),
    ...names.map((n) => {
      const now = planetTropical(n, jd);
      const later = planetTropical(n, jd2);
      const d = norm360(later - now);
      const retro = d > 180;
      return makePlanet(n, now, ayan, retro);
    }),
    makePlanet("Rahu", rahu, ayan, true),
    makePlanet("Ketu", rahu + 180, ayan, true),
  ];
  const lagnaSidereal = norm360(tropicalAscendant(jd) - ayan);
  return { jd, ayan, planets, lagnaSidereal };
}

export function planetByName(planets: PlanetPos[], name: PlanetName): PlanetPos {
  return planets.find((p) => p.name === name)!;
}

export function angularSep(a: number, b: number): number {
  const d = Math.abs(norm360(a - b));
  return d > 180 ? 360 - d : d;
}

export function isKendra(fromSign: number, toSign: number): boolean {
  const d = (toSign - fromSign + 12) % 12;
  return d === 0 || d === 3 || d === 6 || d === 9;
}

export function isTrikona(fromSign: number, toSign: number): boolean {
  const d = (toSign - fromSign + 12) % 12;
  return d === 0 || d === 4 || d === 8;
}
