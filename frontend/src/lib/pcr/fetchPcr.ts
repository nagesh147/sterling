import { api } from "../../utils/api";
import { PCR_INDICES, type PcrDeskPayload, type PcrIndex, type PcrSeries } from "./types";
import { PCR_SNAPSHOT_ISO, snapshotSeries } from "./snapshot";

function snapshotPayload(): PcrDeskPayload {
  const series = {} as Record<PcrIndex, PcrSeries>;
  for (const row of PCR_INDICES) series[row.id] = snapshotSeries(row.id);
  return { asOf: `${PCR_SNAPSHOT_ISO}T15:30:00`, source: "snapshot", series };
}

export async function fetchPcrDesk(): Promise<PcrDeskPayload> {
  try {
    const data = await api.get<PcrDeskPayload>("/api/v1/pcr/session");
    if (!data?.series) return snapshotPayload();
    for (const row of PCR_INDICES) {
      const live = data.series[row.id];
      if (!live?.marks?.length) {
        data.series[row.id] = snapshotSeries(row.id);
      }
    }
    return data;
  } catch {
    return snapshotPayload();
  }
}
