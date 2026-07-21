import React from 'react';
import { SterlingKiteEnginePane } from './SterlingKiteEnginePane';
import {
  useEngineConfig,
  useExpiryCalendar,
  useRunScan,
  useSetEngineConfig,
} from '../../hooks/useSterlingKiteEngine';
import type { EngineConfigModel, ExpiryCalendarEntry, SignalChartData } from '../../types/kiteEngine';
import { k } from '../../styles/kiteUI';
import {
  expiryLabelsForRank,
  type ExpirySeriesKind,
} from './expiryCalendarPresentation';

interface Props {
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number }) => void;
  onOpenChart?: (
    symbol: string,
    tab: 'chart',
    trailTarget?: 'fast' | 'mid' | 'slow',
    signalData?: SignalChartData,
  ) => void;
}

const WEEKLY_RANKS = [0, 1, 2, 3];
const MONTHLY_RANKS = [0, 1];

function ExactExpiryButtons({
  values,
  choices,
  entries,
  kind,
  asOf,
  collapseStocks = false,
  onChange,
}: {
  values: number[];
  choices: number[];
  entries: ExpiryCalendarEntry[];
  kind: ExpirySeriesKind;
  asOf: string;
  collapseStocks?: boolean;
  onChange: (values: number[]) => void;
}) {
  const available = choices.flatMap((rank) => {
    const labels = expiryLabelsForRank(entries, kind, rank, asOf, collapseStocks);
    return labels.length ? [{ rank, labels }] : [];
  });

  if (!available.length) {
    return <span style={{ color: k.dim, fontSize: 10 }}>No listed contracts for the selected instruments</span>;
  }

  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {available.map(({ rank, labels }) => {
        const active = values.includes(rank);
        return (
          <button
            key={`${kind}-${rank}`}
            type="button"
            aria-label={labels.join(', ')}
            aria-pressed={active}
            title={labels.join(' • ')}
            onClick={() => {
              const next = active ? values.filter((value) => value !== rank) : [...values, rank];
              onChange((next.length ? next : [available[0].rank]).sort((a, b) => a - b));
            }}
            style={{
              display: 'grid',
              gap: 2,
              textAlign: 'left',
              border: `1px solid ${active ? k.orange : k.border}`,
              background: active ? '#fff3ed' : k.bg,
              color: active ? k.orange : k.text,
              borderRadius: 5,
              padding: '5px 8px',
              fontSize: 10,
              fontWeight: active ? 700 : 500,
              lineHeight: 1.3,
              cursor: 'pointer',
            }}
          >
            {labels.map((label) => <span key={label}>{label}</span>)}
          </button>
        );
      })}
    </div>
  );
}

function selectedEntries(
  entries: ExpiryCalendarEntry[],
  selected: string[],
): ExpiryCalendarEntry[] {
  const wanted = new Set(selected.map((name) => name.trim().toUpperCase()));
  return entries.filter((entry) => (
    wanted.has(entry.name.toUpperCase()) || wanted.has(entry.display_name.toUpperCase())
  ));
}

export function SterlingKiteEngineWithExpiry(props: Props) {
  const { data } = useEngineConfig();
  const calendar = useExpiryCalendar();
  const setConfig = useSetEngineConfig();
  const runScan = useRunScan();
  const cfg = data as EngineConfigModel | undefined;

  const save = (patch: Partial<EngineConfigModel>) => {
    if (!cfg || setConfig.isPending) return;
    setConfig.mutate({ ...cfg, ...patch }, { onSuccess: () => runScan.mutate() });
  };

  const indexEntries = cfg && calendar.data
    ? selectedEntries(calendar.data.indices, cfg.scan_indices)
    : [];
  const stockEntries = cfg && calendar.data
    ? (cfg.scan_all_stocks
      ? calendar.data.stocks
      : selectedEntries(calendar.data.stocks, cfg.scan_stocks))
    : [];

  return (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      {cfg && (
        <section
          aria-label="Option contract expiries"
          style={{
            flexShrink: 0,
            borderBottom: `1px solid ${k.border}`,
            background: k.bg,
            padding: '9px 10px',
            display: 'grid',
            gap: 8,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'baseline' }}>
            <strong style={{ fontSize: 11, color: k.text }}>Exact option contracts</strong>
            <span style={{ fontSize: 9, color: k.dim }}>Live dates from Kite instruments</span>
          </div>

          {calendar.isLoading && (
            <div role="status" style={{ fontSize: 10, color: k.dim }}>Loading listed contract dates…</div>
          )}
          {calendar.isError && (
            <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, color: k.dim }}>
              <span>Exact expiry dates are unavailable. Check the Kite connection and retry.</span>
              <button type="button" onClick={() => calendar.refetch()} style={{ fontSize: 10, cursor: 'pointer' }}>
                Retry
              </button>
            </div>
          )}

          {calendar.data && (
            <div style={{ display: 'grid', gridTemplateColumns: '124px minmax(0, 1fr)', gap: 7, alignItems: 'center' }}>
              <strong style={{ fontSize: 10, color: k.text }}>Weekly index expiries</strong>
              <ExactExpiryButtons
                kind="weekly"
                choices={WEEKLY_RANKS}
                entries={indexEntries}
                asOf={calendar.data.as_of}
                values={cfg.scan_weekly_series_indices ?? WEEKLY_RANKS}
                onChange={(values) => save({ scan_weekly_series_indices: values })}
              />

              <strong style={{ fontSize: 10, color: k.text }}>Monthly index expiries</strong>
              <ExactExpiryButtons
                kind="monthly"
                choices={MONTHLY_RANKS}
                entries={indexEntries}
                asOf={calendar.data.as_of}
                values={cfg.scan_monthly_series_indices ?? MONTHLY_RANKS}
                onChange={(values) => save({ scan_monthly_series_indices: values })}
              />

              <strong style={{ fontSize: 10, color: k.text }}>Monthly stock expiries</strong>
              <ExactExpiryButtons
                kind="monthly"
                choices={MONTHLY_RANKS}
                entries={stockEntries}
                asOf={calendar.data.as_of}
                collapseStocks
                values={cfg.scan_monthly_series_stocks ?? MONTHLY_RANKS}
                onChange={(values) => save({ scan_monthly_series_stocks: values })}
              />
            </div>
          )}

          <div style={{ fontSize: 9, color: k.dim }}>
            Expired contracts disappear automatically. Sterling never invents a weekday or holiday-adjusted expiry.
          </div>
        </section>
      )}
      <div style={{ flex: 1, minHeight: 0 }}>
        <SterlingKiteEnginePane {...props} />
      </div>
    </div>
  );
}

export default SterlingKiteEngineWithExpiry;
