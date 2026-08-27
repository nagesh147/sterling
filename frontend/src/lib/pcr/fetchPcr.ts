import { api } from "../../utils/api";
import { PCR_INDICES, type PcrDeskPayload, type PcrIndex, type PcrSeries } from "./types";
import { overlayShot, SHOT_2026_08_27, SHOT_SESSION_ISO } from "./slots";
import { PCR_SNAPSHOT_ISO, snapshotSeries } from "./snapshot";

function snapshotPayload(): PcrDeskPayload {
  const series = {} as Record<PcrIndex, PcrSeries>;
  for (const row of PCR_INDICES) series[row.id] = snapshotSeries(row.id);
  return { asOf: `${PCR_SNAPSHOT_ISO}T15:30:00`, source: "snapshot", series };
}

function sessionIso(series: PcrSeries): string {
  return (series.spot?.timestamp || "").slice(0, 10);
}

export async function fetchPcrDesk(): Promise<PcrDeskPayload> {
  try {
    const data = await api.get<PcrDeskPayload>("/api/v1/pcr/session");
    if (!data?.series) return snapshotPayload();
    for (const row of PCR_INDICES) {
      const live = data.series[row.id];
      if (!live?.marks?.length) {
        data.series[row.id] = snapshotSeries(row.id);
      } else if (sessionIso(live) === SHOT_SESSION_ISO) {
        live.marks = overlayShot(live.marks, SHOT_2026_08_27[row.id]);
      }
    }
    return data;
  } catch {
    return snapshotPayload();
  }
}