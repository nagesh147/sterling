import React from 'react';
import { SterlingKiteEnginePane } from './SterlingKiteEnginePane';
import {
  useEngineConfig,
  useRunScan,
  useSetEngineConfig,
} from '../../hooks/useSterlingKiteEngine';
import type { EngineConfigModel, SignalChartData } from '../../types/kiteEngine';
import { k } from '../../styles/kiteUI';

type SeriesConfig = EngineConfigModel & {
  scan_weekly_series_indices?: number[];
  scan_monthly_series_indices?: number[];
  scan_weekly_series_stocks?: number[];
  scan_monthly_series_stocks?: number[];
};

interface Props {
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number }) => void;
  onOpenChart?: (
    symbol: string,
    tab: 'chart',
    trailTarget?: 'fast' | 'mid' | 'slow',
    signalData?: SignalChartData,
  ) => void;
}

const WEEKLY = [0, 1, 2, 3];
const MONTHLY = [0, 1];

function SeriesButtons({
  values,
  choices,
  prefix,
  onChange,
}: {
  values: number[];
  choices: number[];
  prefix: 'W' | 'M';
  onChange: (values: number[]) => void;
}) {
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {choices.map((rank) => {
        const active = values.includes(rank);
        const label = prefix === 'W'
          ? `W${rank + 1}`
          : rank === 0 ? 'M1 Current' : 'M2 Next';
        return (
          <button
            key={`${prefix}-${rank}`}
            type="button"
            title={prefix === 'W'
              ? `${rank + 1}${rank === 0 ? 'st' : rank === 1 ? 'nd' : rank === 2 ? 'rd' : 'th'} listed weekly expiry`
              : rank === 0 ? 'Nearest listed monthly expiry' : 'Next listed monthly expiry'}
            onClick={() => {
              const next = active ? values.filter((v) => v !== rank) : [...values, rank];
              onChange((next.length ? next : [0]).sort((a, b) => a - b));
            }}
            style={{
              border: `1px solid ${active ? k.orange : k.border}`,
              background: active ? '#fff3ed' : k.bg,
              color: active ? k.orange : k.text,
              borderRadius: 4,
              padding: '4px 7px',
              fontSize: 10,
              fontWeight: active ? 700 : 500,
              cursor: 'pointer',
            }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

export function SterlingKiteEngineWithExpiry(props: Props) {
  const { data } = useEngineConfig();
  const setConfig = useSetEngineConfig();
  const runScan = useRunScan();
  const cfg = data as SeriesConfig | undefined;

  const save = (patch: Partial<SeriesConfig>) => {
    if (!cfg || setConfig.isPending) return;
    const next = { ...cfg, ...patch } as EngineConfigModel;
    setConfig.mutate(next, { onSuccess: () => runScan.mutate() });
  };

  return (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      {cfg && (
        <section
          aria-label="Option expiry series"
          style={{
            flexShrink: 0,
            borderBottom: `1px solid ${k.border}`,
            background: k.bg,
            padding: '8px 10px',
            display: 'grid',
            gap: 7,
          }}
        >
          <div style={{ fontSize: 10, lineHeight: 1.35, color: k.dim }}>
            Expiries are read exactly from Kite's listed instrument dump. No weekday or holiday date is guessed.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '66px 1fr', gap: 6, alignItems: 'center' }}>
            <strong style={{ fontSize: 10, color: k.text }}>Index weeks</strong>
            <SeriesButtons
              prefix="W"
              choices={WEEKLY}
              values={cfg.scan_weekly_series_indices ?? WEEKLY}
              onChange={(values) => save({ scan_weekly_series_indices: values })}
            />
            <strong style={{ fontSize: 10, color: k.text }}>Index months</strong>
            <SeriesButtons
              prefix="M"
              choices={MONTHLY}
              values={cfg.scan_monthly_series_indices ?? MONTHLY}
              onChange={(values) => save({ scan_monthly_series_indices: values })}
            />
            <strong style={{ fontSize: 10, color: k.text }}>Stock months</strong>
            <SeriesButtons
              prefix="M"
              choices={MONTHLY}
              values={cfg.scan_monthly_series_stocks ?? MONTHLY}
              onChange={(values) => save({ scan_monthly_series_stocks: values })}
            />
          </div>
          <div style={{ fontSize: 9, color: k.dim }}>
            Stocks are monthly-only. A selected series that is not listed resolves to no contract; it never falls back to an invented date.
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
