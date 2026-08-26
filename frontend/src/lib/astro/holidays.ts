/** Artifact A3 — NSE equity trading calendar (weekends + published 2026 holidays). */

export const NSE_HOLIDAYS_2026: Record<string, string> = {
  "2026-01-15": "Municipal Corporation Election — Maharashtra",
  "2026-01-26": "Republic Day",
  "2026-03-03": "Holi",
  "2026-03-26": "Shri Ram Navami",
  "2026-03-31": "Shri Mahavir Jayanti",
  "2026-04-03": "Good Friday",
  "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
  "2026-05-01": "Maharashtra Day",
  "2026-05-28": "Bakri Id",
  "2026-06-26": "Muharram",
  "2026-09-14": "Ganesh Chaturthi",
  "2026-10-02": "Mahatma Gandhi Jayanti",
  "2026-10-20": "Dussehra",
  "2026-11-10": "Diwali — Balipratipada",
  "2026-11-24": "Guru Nanak Jayanti",
  "2026-12-25": "Christmas",
};

export const MUHURAT_SESSIONS: Record<string, string> = {
  "2026-11-08": "Diwali Muhurat Trading (special session)",
};

export function holidayName(isoDate: string): string | undefined {
  return NSE_HOLIDAYS_2026[isoDate];
}

export function isNseHoliday(isoDate: string): boolean {
  return isoDate in NSE_HOLIDAYS_2026;
}

export function isMuhurat(isoDate: string): boolean {
  return isoDate in MUHURAT_SESSIONS;
}
