/** Artifact A2 — IST clock, Julian day, market minutes. All astrology is Mumbai / IST. */

export const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000;
export const MUMBAI = { lat: 18.9388, lon: 72.8354 };

export function istFromUtc(date: Date): Date {
  return new Date(date.getTime() + IST_OFFSET_MS);
}

export function utcFromIstParts(
  year: number,
  month: number,
  day: number,
  hour = 0,
  minute = 0,
  second = 0,
): Date {
  return new Date(Date.UTC(year, month - 1, day, hour, minute, second) - IST_OFFSET_MS);
}

export interface IstParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
  weekday: number;
}

export function getIstParts(date: Date): IstParts {
  const ist = istFromUtc(date);
  return {
    year: ist.getUTCFullYear(),
    month: ist.getUTCMonth() + 1,
    day: ist.getUTCDate(),
    hour: ist.getUTCHours(),
    minute: ist.getUTCMinutes(),
    second: ist.getUTCSeconds(),
    weekday: ist.getUTCDay(),
  };
}

export function formatIstDate(date: Date): string {
  const p = getIstParts(date);
  const dd = String(p.day).padStart(2, "0");
  const mm = String(p.month).padStart(2, "0");
  const yy = String(p.year).slice(-2);
  return `${dd}-${mm}-${yy}`;
}

export function formatIstIsoDate(date: Date): string {
  const p = getIstParts(date);
  return `${p.year}-${String(p.month).padStart(2, "0")}-${String(p.day).padStart(2, "0")}`;
}

export function formatClock(hour: number, minute: number): string {
  const h24 = ((hour % 24) + 24) % 24;
  const h12 = h24 % 12 === 0 ? 12 : h24 % 12;
  const ampm = h24 < 12 ? "AM" : "PM";
  return `${h12}:${String(minute).padStart(2, "0")} ${ampm}`;
}

export function minutesOfDay(hour: number, minute: number): number {
  return hour * 60 + minute;
}

export function clockFromMinutes(mins: number): string {
  const clamped = ((mins % 1440) + 1440) % 1440;
  return formatClock(Math.floor(clamped / 60), clamped % 60);
}

export function julianDate(date: Date): number {
  const y0 = date.getUTCFullYear();
  let m = date.getUTCMonth() + 1;
  const day =
    date.getUTCDate() +
    date.getUTCHours() / 24 +
    date.getUTCMinutes() / 1440 +
    date.getUTCSeconds() / 86400 +
    date.getUTCMilliseconds() / 86400000;
  let y = y0;
  if (m <= 2) {
    y -= 1;
    m += 12;
  }
  const A = Math.floor(y / 100);
  const B = 2 - A + Math.floor(A / 4);
  return Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + day + B - 1524.5;
}

export function startOfIstDay(date: Date): Date {
  const p = getIstParts(date);
  return utcFromIstParts(p.year, p.month, p.day, 0, 0, 0);
}

export const MARKET_OPEN_MIN = 9 * 60 + 15;
export const MARKET_CLOSE_MIN = 15 * 60 + 30;

export const SLOT_STARTS: [number, number][] = [
  [9, 15],
  [9, 45],
  [10, 15],
  [10, 45],
  [11, 15],
  [11, 45],
  [12, 15],
  [12, 45],
  [13, 15],
  [13, 45],
  [14, 15],
  [14, 45],
  [15, 15],
];
