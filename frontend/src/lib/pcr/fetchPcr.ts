import { api } from "../../utils/api";
import { PCR_SNAPSHOT_ISO, snapshotSeries } from "./snapshot";
import { PCR_INDICES, type PcrDeskPayload, type PcrIndex, type PcrSeries } from "./types";

const STORE = "sterling.pcr.books.v1";

function snapshotPayload(): PcrDeskPayload {
  const series = {} as Record<PcrIndex, PcrSeries>;
  for (const row of PCR_INDICES) series[row.id] = snapshotSeries(row.id);
  return { asOf: `${PCR_SNAPSHOT_ISO}T15:30:00`, source: "snapshot", series };
}

export function sessionIsoOf(payload: PcrDeskPayload): string {
  const ts = payload.series?.NIFTY?.spot?.timestamp || payload.asOf || "";
  return ts.slice(0, 10);
}

function readBooks(): Record<string, PcrDeskPayload> {
  try {
    const raw = localStorage.getItem(STORE);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, PcrDeskPayload>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeBooks(books: Record<string, PcrDeskPayload>) {
  try {
    localStorage.setItem(STORE, JSON.stringify(books));
  } catch {
    /* quota */
  }
}

export function rememberSession(payload: PcrDeskPayload) {
  const iso = sessionIsoOf(payload);
  if (!iso) return;
  const books = readBooks();
  books[iso] = payload;
  writeBooks(books);
}

export function recallSession(iso: string): PcrDeskPayload | null {
  if (iso === PCR_SNAPSHOT_ISO) return snapshotPayload();
  return readBooks()[iso] ?? null;
}

function emptyPayload(iso: string): PcrDeskPayload {
  return { asOf: `${iso}T00:00:00`, source: "snapshot", series: {} as Record<PcrIndex, PcrSeries> };
}

export async function fetchPcrDesk(sessionIso?: string | null): Promise<PcrDeskPayload> {
  try {
    const data = await api.get<PcrDeskPayload>("/api/v1/pcr/session");
    if (data?.series && Object.keys(data.series).length) {
      rememberSession(data);
      const liveIso = sessionIsoOf(data);
      if (!sessionIso || sessionIso === liveIso) return data;
    }
  } catch {
    /* fall through to stored / snapshot */
  }
  if (sessionIso) {
    const stored = recallSession(sessionIso);
    if (stored) return stored;
    return emptyPayload(sessionIso);
  }
  return snapshotPayload();
}
