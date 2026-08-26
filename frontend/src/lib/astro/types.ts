/** Artifact A1 — domain model for the Financial Astrology desk. */

export type Underlying = "NIFTY" | "BANKNIFTY" | "FINNIFTY" | "SENSEX" | "MIDCPNIFTY";

export type GapKind = "up" | "flat" | "down";

export type Regime =
  | "Strong Positive"
  | "Positive"
  | "Volatile Positive"
  | "Sideways to Positive"
  | "Sideways/Volatile"
  | "Sideways to Negative"
  | "Volatile Negative"
  | "Negative"
  | "Strong Negative";

export type TradeSide = "CE" | "PE" | "BOTH" | "WAIT";

export type TradeAction =
  | "BUY CE"
  | "BUY PE"
  | "SCALP CE"
  | "SCALP PE"
  | "STRADDLE"
  | "IRON FLY"
  | "HOLD CE"
  | "HOLD PE"
  | "BOOK CE"
  | "BOOK PE"
  | "AVOID"
  | "WAIT";

export type PlanetName =
  | "Sun"
  | "Moon"
  | "Mercury"
  | "Venus"
  | "Mars"
  | "Jupiter"
  | "Saturn"
  | "Rahu"
  | "Ketu";

export type AspectKind = "conjunction" | "opposition" | "square" | "trine" | "sextile";

export interface AspectHit {
  a: PlanetName;
  b: PlanetName;
  kind: AspectKind;
  orb: number;
  note: string;
}

export type DignityKind = "exalted" | "debilitated" | "own" | "moolatrikona" | "friend" | "neutral" | "enemy";

export interface DignityHit {
  name: PlanetName;
  dignity: DignityKind;
  label: string;
}

export interface PlanetPos {
  name: PlanetName;
  tropical: number;
  sidereal: number;
  sign: string;
  signIndex: number;
  degreeInSign: number;
  retrograde: boolean;
}

export interface Panchang {
  weekday: string;
  weekdayIndex: number;
  tithiIndex: number;
  tithiName: string;
  paksha: "Shukla" | "Krishna";
  nakshatraIndex: number;
  nakshatra: string;
  nakshatraPada: number;
  nakshatraLord: PlanetName;
  yogaIndex: number;
  yoga: string;
  karana: string;
  moonSign: string;
  sunSign: string;
  lagnaSign: string;
  lagnaDegree: number;
  sunriseIso: string;
  sunsetIso: string;
}

export interface HoraInfo {
  lord: PlanetName;
  index: number;
  startsAt: string;
  endsAt: string;
}

export interface KalamFlag {
  rahu: boolean;
  yamagandam: boolean;
  gulika: boolean;
}

export interface GapCall {
  kind: GapKind;
  label: string;
  confidence: number;
  volatility: "low" | "medium" | "high" | "extreme";
  bias: "bullish" | "neutral" | "bearish";
  openAction: TradeAction;
  summary: string;
  reasons: string[];
  firstHourNote: string;
  horaAtOpen: PlanetName;
  yogas: string[];
  eclipse: boolean;
  gandanta: boolean;
}

export interface WindowSlot {
  date: string;
  from: string;
  to: string;
  fromMin: number;
  toMin: number;
  hora: PlanetName;
  lagna: string;
  nakshatra: string;
  regime: Regime;
  action: TradeAction;
  side: TradeSide;
  product: string;
  suggestion: string;
  strength: number;
  confidence: number;
  kalam: KalamFlag;
  why: string;
  isLive: boolean;
  isPast: boolean;
  choghadiya: string;
  choghadiyaKind: "good" | "move" | "bad";
  abhijit: boolean;
}

export interface DayPlaybook {
  date: string;
  weekday: string;
  underlying: Underlying;
  gap: GapCall;
  panchang: Panchang;
  bestCe: WindowSlot | null;
  bestPe: WindowSlot | null;
  avoid: WindowSlot[];
  closeBias: Regime;
  headline: string;
  horaAtOpen: PlanetName;
}

export interface MonthDay {
  date: string;
  weekday: string;
  isWeekend: boolean;
  isHoliday: boolean;
  holidayName?: string;
  isToday: boolean;
  gap: GapKind | null;
  gapLabel: string;
  bias: "bullish" | "neutral" | "bearish" | null;
  volatility: "low" | "medium" | "high" | "extreme" | null;
  regime: Regime | null;
  openAction: TradeAction | null;
  confidence: number;
  note: string;
}

export interface MonthProjection {
  year: number;
  month: number;
  label: string;
  days: MonthDay[];
  tradingDays: number;
  gapUp: number;
  gapDown: number;
  gapFlat: number;
  bullishDays: number;
  bearishDays: number;
  summary: string;
}

export interface DayForecast {
  date: string;
  underlying: Underlying;
  generatedAt: string;
  panchang: Panchang;
  planets: PlanetPos[];
  gap: GapCall;
  playbook: DayPlaybook;
  slots: WindowSlot[];
  netResults: WindowSlot[];
  aspects: AspectHit[];
  dignities: DignityHit[];
}

export const UNDERLYINGS: { id: Underlying; label: string; step: number }[] = [
  { id: "NIFTY", label: "Nifty 50", step: 50 },
  { id: "BANKNIFTY", label: "Bank Nifty", step: 100 },
  { id: "FINNIFTY", label: "Fin Nifty", step: 50 },
  { id: "SENSEX", label: "Sensex", step: 100 },
  { id: "MIDCPNIFTY", label: "Midcap Nifty", step: 25 },
];

export const SIGNS = [
  "Aries",
  "Taurus",
  "Gemini",
  "Cancer",
  "Leo",
  "Virgo",
  "Libra",
  "Scorpio",
  "Sagittarius",
  "Capricorn",
  "Aquarius",
  "Pisces",
] as const;

export const NAKSHATRAS = [
  "Ashwini",
  "Bharani",
  "Krittika",
  "Rohini",
  "Mrigashira",
  "Ardra",
  "Punarvasu",
  "Pushya",
  "Ashlesha",
  "Magha",
  "Purva Phalguni",
  "Uttara Phalguni",
  "Hasta",
  "Chitra",
  "Swati",
  "Vishakha",
  "Anuradha",
  "Jyeshtha",
  "Mula",
  "Purva Ashadha",
  "Uttara Ashadha",
  "Shravana",
  "Dhanishta",
  "Shatabhisha",
  "Purva Bhadrapada",
  "Uttara Bhadrapada",
  "Revati",
] as const;

export const NAKSHATRA_LORDS: PlanetName[] = [
  "Ketu",
  "Venus",
  "Sun",
  "Moon",
  "Mars",
  "Rahu",
  "Jupiter",
  "Saturn",
  "Mercury",
  "Ketu",
  "Venus",
  "Sun",
  "Moon",
  "Mars",
  "Rahu",
  "Jupiter",
  "Saturn",
  "Mercury",
  "Ketu",
  "Venus",
  "Sun",
  "Moon",
  "Mars",
  "Rahu",
  "Jupiter",
  "Saturn",
  "Mercury",
];

export const YOGAS = [
  "Vishkambha",
  "Priti",
  "Ayushman",
  "Saubhagya",
  "Shobhana",
  "Atiganda",
  "Sukarma",
  "Dhriti",
  "Shoola",
  "Ganda",
  "Vriddhi",
  "Dhruva",
  "Vyaghata",
  "Harshana",
  "Vajra",
  "Siddhi",
  "Vyatipata",
  "Variyan",
  "Parigha",
  "Shiva",
  "Siddha",
  "Sadhya",
  "Shubha",
  "Shukla",
  "Brahma",
  "Indra",
  "Vaidhriti",
];

export const TITHI_NAMES = [
  "Pratipada",
  "Dwitiya",
  "Tritiya",
  "Chaturthi",
  "Panchami",
  "Shashthi",
  "Saptami",
  "Ashtami",
  "Navami",
  "Dashami",
  "Ekadashi",
  "Dwadashi",
  "Trayodashi",
  "Chaturdashi",
  "Purnima",
];

export const KARANAS = [
  "Bava",
  "Balava",
  "Kaulava",
  "Taitila",
  "Garaja",
  "Vanija",
  "Vishti",
  "Shakuni",
  "Chatushpada",
  "Naga",
  "Kimstughna",
];

export const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export const WEEKDAY_LORDS: PlanetName[] = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"];
