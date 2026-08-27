/** Intraday + Weekly Put-Call Ratio desk. */

export type PcrIndex = "NIFTY" | "BANKNIFTY" | "FINNIFTY" | "SENSEX" | "MIDCPNIFTY";

export const PCR_INDICES: { id: PcrIndex; label: string; short: string }[] = [
  { id: "NIFTY", label: "Nifty", short: "Nifty" },
  { id: "BANKNIFTY", label: "Bank Nifty", short: "Bank" },
  { id: "FINNIFTY", label: "Fin Nifty", short: "Fin" },
  { id: "SENSEX", label: "Sensex", short: "Sensex" },
  { id: "MIDCPNIFTY", label: "Midcap Nifty", short: "Midcap" },
];

export type PcrMetric = "oi" | "volume" | "changeOi";

export type PcrBand =
  | "extreme-positive"
  | "highly-positive"
  | "positive"
  | "negative"
  | "highly-negative"
  | "extreme-negative"
  | "empty";

export interface PcrTick {
  time: string;
  pcr: number;
  volumePcr: number;
  changeOiPcr: number;
  indexClose: number;
  expiry: string;
}

export interface PcrMark {
  hhmm: string;
  pcr: number;
  volumePcr: number;
  changeOiPcr: number;
  indexClose: number;
}

export interface PcrSpot {
  ltp: number | null;
  changePer: number | null;
  maxPain: number | null;
  vix: number | null;
  timestamp: string | null;
}

export interface PcrSeries {
  id: PcrIndex;
  expiry: string;
  livePcr: number | null;
  spot: PcrSpot;
  marks: PcrMark[];
  latest: PcrMark | null;
}

export interface PcrSlot {
  hhmm: string;
  label: string;
  minutes: number;
  pcr: number | null;
  delta: number | null;
  band: PcrBand;
  live: boolean;
}

export interface PcrDeskPayload {
  asOf: string;
  source: "live" | "snapshot";
  series: Record<PcrIndex, PcrSeries>;
}
