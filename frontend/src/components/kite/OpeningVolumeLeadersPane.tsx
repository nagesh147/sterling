import { useMemo, useState } from 'react';
import {
  useOpeningVolumeContract,
  useOpeningVolumeScan,
  type OpeningLeaderDirection,
  type OpeningLeaderSignal,
  type OpeningLeaderTier,
} from '../../hooks/useOpeningVolumeLeaders';
import { OPENING_VOLUME_LEADERS_CSS } from './openingVolumeLeadersCss';

type Scope = 'all' | 'custom';
type DirectionFilter = 'ALL' | OpeningLeaderDirection;
type TierFilter = 'all' | Exclude<OpeningLeaderTier, 'weak'>;

const TIER_ORDER: Array<{ id: TierFilter; label: string }> = [
  { id: 'all', label: 'All tiers' },
  { id: 'explosive', label: 'Explosive' },
  { id: 'strong', label: 'Strong' },
  { id: 'spurt', label: 'Spurt' },
  { id: 'watch', label: 'Watch' },
];

const TIME_FORMAT = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const DATE_TIME_FORMAT = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

function safeDate(value: string): Date | null {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatTime(value: string | null): string {
  if (!value) return 'Not broken';
  const parsed = safeDate(value);
  return parsed ? `${TIME_FORMAT.format(parsed)} IST` : '—';
}

function formatDateTime(value: string): string {
  const parsed = safeDate(value);
  return parsed ? `${DATE_TIME_FORMAT.format(parsed)} IST` : '—';
}

function formatNumber(value: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return value.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function formatCompact(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

function formatPct(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value >= 0 ? '+' : ''}${formatNumber(value)}%`;
}

function formatTurnover(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return 'Unknown';
  if (value >= 10_000_000) return `₹${formatNumber(value / 10_000_000)} Cr`;
  if (value >= 100_000) return `₹${formatNumber(value / 100_000)} L`;
  return `₹${formatCompact(value)}`;
}

function label(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function parseSymbols(value: string): string[] {
  return Array.from(new Set(value.split(/[\s,]+/).map((symbol) => symbol.trim().toUpperCase()).filter(Boolean)));
}

function DirectionArrow({ direction }: { direction: OpeningLeaderDirection }) {
  if (direction === 'NEUTRAL') return <span aria-hidden="true">—</span>;
  return <span aria-hidden="true">{direction === 'UP' ? '↑' : '↓'}</span>;
}

function Stat({ name, value, detail }: { name: string; value: string | number; detail: string }) {
  return (
    <div className="ovl-stat">
      <span>{name}</span>
      <strong>{value}</strong>
      <small title={detail}>{detail}</small>
    </div>
  );
}

function SignalCard({
  signal,
  rank,
  onOpenChart,
}: {
  signal: OpeningLeaderSignal;
  rank: number;
  onOpenChart?: (symbol: string) => void;
}) {
  const priceTone = signal.day_change_pct == null ? undefined : signal.day_change_pct >= 0 ? 'up' : 'down';
  const orbSide = signal.orb_break_side ? `${signal.orb_break_side} ${signal.orb_aligned ? '· aligned' : '· counter'}` : 'No confirmed side';
  const moveLabel = signal.direction === 'DOWN' ? 'From high' : 'From low';
  const moveValue = signal.direction === 'DOWN' ? -signal.fall_from_high_pct : signal.rise_from_low_pct;
  const liquidityTitle = signal.liquidity_reasons.length
    ? signal.liquidity_reasons.join('; ')
    : `20-session average turnover ${formatTurnover(signal.average_turnover_inr)}`;

  return (
    <article className="ovl-card ovl-panel" data-direction={signal.direction} aria-label={`${signal.symbol} ${signal.tier} ${signal.direction}`}>
      <div className="ovl-card-top">
        <div style={{ minWidth: 0 }}>
          <h3 className="ovl-symbol"><span className="ovl-rank">#{rank}</span>{signal.symbol}</h3>
          <div className="ovl-direction"><DirectionArrow direction={signal.direction} /> {signal.direction}</div>
        </div>
        <div className="ovl-rvol">
          <strong>{formatNumber(signal.rvol)}×</strong>
          <span>09:15 RVOL</span>
        </div>
      </div>

      <div className="ovl-badges">
        <span className="ovl-badge" data-tier={signal.tier}>{signal.tier}</span>
        {signal.combo && <span className="ovl-badge" data-combo="true">Combo</span>}
        {signal.passes_quality_filters && <span className="ovl-badge">Quality pass</span>}
        {signal.orb_immediate && <span className="ovl-badge">09:16 ORB</span>}
      </div>

      <div className="ovl-tape">
        <div>
          <span>LTP</span>
          <strong>₹{formatNumber(signal.current_price)}</strong>
        </div>
        <div>
          <span>Day</span>
          <strong data-tone={priceTone}>{formatPct(signal.day_change_pct)}</strong>
        </div>
        <div>
          <span>{moveLabel}</span>
          <strong data-tone={moveValue >= 0 ? 'up' : 'down'}>{formatPct(moveValue)}</strong>
        </div>
      </div>

      <div className="ovl-evidence">
        <div className="ovl-event">
          <span>Signal</span>
          <strong>{formatTime(signal.signal_time)} <em>· {formatCompact(signal.opening_volume)} vs {formatCompact(signal.average_opening_volume)} avg · {signal.baseline_session_count} sessions</em></strong>
        </div>
        <div className="ovl-event">
          <span>ORB</span>
          <strong>{formatTime(signal.orb_break_time)} <em>· {orbSide}{signal.orb_cumulative_volume != null ? ` · ${formatCompact(signal.orb_cumulative_volume)} vol` : ''}</em></strong>
        </div>
      </div>

      <div className="ovl-card-foot">
        <span className="ovl-state" data-state={signal.liquidity_state} title={liquidityTitle}><i />Liquidity {signal.liquidity_state}</span>
        {onOpenChart && <button type="button" className="ovl-chart" onClick={() => onOpenChart(signal.symbol)}>Chart</button>}
        <span className="ovl-quality">{signal.candle_quality} candle · {label(signal.entry_phase)}</span>
      </div>

      <details className="ovl-details">
        <summary>Opening candle &amp; filter evidence</summary>
        <div className="ovl-detail-grid">
          <div><span>Open</span><strong>₹{formatNumber(signal.opening_open)}</strong></div>
          <div><span>High</span><strong>₹{formatNumber(signal.opening_high)}</strong></div>
          <div><span>Low</span><strong>₹{formatNumber(signal.opening_low)}</strong></div>
          <div><span>Close</span><strong>₹{formatNumber(signal.opening_close)}</strong></div>
          <div><span>Gap</span><strong>{formatPct(signal.gap_pct)}</strong></div>
          <div><span>Body / range</span><strong>{formatNumber(signal.body_pct)}% / {formatNumber(signal.range_pct)}%</strong></div>
          <div><span>Body fraction</span><strong>{formatNumber(signal.body_fraction * 100, 1)}%</strong></div>
          <div><span>Close location</span><strong>{formatNumber(signal.close_location * 100, 1)}%</strong></div>
          <div><span>Avg turnover</span><strong>{formatTurnover(signal.average_turnover_inr)}</strong></div>
          {signal.liquidity_reasons.length > 0 && <div className="ovl-reason">{signal.liquidity_reasons.join(' · ')}</div>}
        </div>
      </details>
    </article>
  );
}

export interface OpeningVolumeLeadersPaneProps {
  onOpenChart?: (symbol: string) => void;
}

export function OpeningVolumeLeadersPane({ onOpenChart }: OpeningVolumeLeadersPaneProps) {
  const contract = useOpeningVolumeContract();
  const scan = useOpeningVolumeScan();
  const [scope, setScope] = useState<Scope>('all');
  const [symbolsText, setSymbolsText] = useState('');
  const [includeWatch, setIncludeWatch] = useState(false);
  const [maxCandidates, setMaxCandidates] = useState(250);
  const [formError, setFormError] = useState<string | null>(null);
  const [direction, setDirection] = useState<DirectionFilter>('ALL');
  const [tier, setTier] = useState<TierFilter>('all');
  const [search, setSearch] = useState('');

  const runScan = () => {
    const symbols = parseSymbols(symbolsText);
    if (scope === 'custom' && symbols.length === 0) {
      setFormError('Enter at least one current F&O equity symbol.');
      return;
    }
    setFormError(null);
    scan.mutate({
      symbols: scope === 'custom' ? symbols : [],
      scan_all_stocks: scope === 'all',
      include_watch: includeWatch,
      max_candidates: maxCandidates,
      concurrency: 3,
      history_calendar_days: 45,
      config: {},
    });
  };

  const data = scan.data;
  const candidates = useMemo(
    () => data ? [...data.leaders, ...data.watch] : [],
    [data],
  );
  const filtered = useMemo(() => {
    const query = search.trim().toUpperCase();
    return candidates.filter((signal) => (
      (direction === 'ALL' || signal.direction === direction)
      && (tier === 'all' || signal.tier === tier)
      && (!query || signal.symbol.includes(query))
    ));
  }, [candidates, direction, tier, search]);

  const version = contract.data?.strategy.version ?? data?.strategy.version;
  const contractError = contract.error instanceof Error ? contract.error.message : null;
  const scanError = scan.error instanceof Error ? scan.error.message : null;
  const sourceLabel = data?.universe.source.replace(/_/g, ' ') ?? 'Current Kite F&O equities';

  return (
    <main className="ovl-root">
      <style>{OPENING_VOLUME_LEADERS_CSS}</style>
      <div className="ovl-shell">
        <header className="ovl-header">
          <div>
            <p className="ovl-eyebrow">Opening volume · 1-minute cash candles</p>
            <h1 className="ovl-title">Opening Leaders</h1>
            <p className="ovl-subtitle">Find F&amp;O stocks whose completed 09:15 volume is abnormal versus the same minute over the prior 10 sessions, then verify direction, liquidity, candle quality, and the first opening-range break.</p>
            <div className="ovl-contract" aria-label="Strategy contract">
              <span><strong>{version ? `Contract v${version}` : 'Loading contract'}</strong></span>
              <span>SPURT 3× · STRONG 5× · EXPLOSIVE 10×</span>
              <span>No proprietary score</span>
              {contractError && <span title={contractError}>Contract metadata unavailable</span>}
            </div>
          </div>
          <span className="ovl-advisory"><i />Advisory only</span>
        </header>

        <section className="ovl-panel" aria-label="Opening leader scan controls">
          <div className="ovl-toolbar">
            <div className="ovl-control">
              <span>Universe</span>
              <span className="ovl-segment">
                <button type="button" data-on={scope === 'all'} onClick={() => setScope('all')}>All F&amp;O</button>
                <button type="button" data-on={scope === 'custom'} onClick={() => setScope('custom')}>Custom</button>
              </span>
            </div>
            <label className="ovl-control">
              <span>Max stocks</span>
              <select className="ovl-select" value={maxCandidates} onChange={(event) => setMaxCandidates(Number(event.target.value))}>
                {[50, 100, 250, 500].map((count) => <option key={count} value={count}>{count}</option>)}
              </select>
            </label>
            <label className="ovl-check">
              <input type="checkbox" checked={includeWatch} onChange={(event) => setIncludeWatch(event.target.checked)} />
              Include 2–3× watchlist
            </label>
            <button type="button" className="ovl-scan" disabled={scan.isPending} onClick={runScan}>
              {scan.isPending && <span className="ovl-spinner" />}
              {scan.isPending ? 'Scanning…' : data ? 'Run again' : 'Run opening scan'}
            </button>
          </div>
          {scope === 'custom' && (
            <div className="ovl-scope-input">
              <label className="ovl-control">
                <span>Current F&amp;O equity symbols · comma or space separated</span>
                <input className="ovl-input" value={symbolsText} onChange={(event) => setSymbolsText(event.target.value)} placeholder="RBLBANK, GODREJCP, PAGEIND" />
              </label>
            </div>
          )}
          {formError && <p role="alert" className="ovl-form-error">{formError}</p>}
        </section>

        {scan.isPending && (
          <section className="ovl-panel ovl-progress" aria-live="polite">
            <span className="ovl-spinner" />
            <strong>Reading the opening candle history</strong>
            <p>The full-universe scan is broker-rate-limited and can take about 1–2 minutes. This page does not place or prepare any order.</p>
          </section>
        )}

        {!scan.isPending && scanError && <section role="alert" className="ovl-panel ovl-error"><strong>Scan failed.</strong> {scanError}</section>}

        {!scan.isPending && !data && !scanError && (
          <section className="ovl-panel ovl-empty">
            <div className="ovl-empty-icon" aria-hidden="true">↗</div>
            <h2>Ready for the completed 09:15 candle</h2>
            <p>Run after 09:16 IST with an active Kite session. Results use current broker-listed single-stock F&amp;O names; index options and stale symbols are excluded.</p>
          </section>
        )}

        {!scan.isPending && data && (
          <>
            <section className="ovl-panel ovl-stats" aria-label="Scan summary">
              <Stat name="Universe" value={`${data.evaluated_count}/${data.universe_count}`} detail={data.universe.truncated ? `${data.universe.available_fno_equity_count} available · capped` : sourceLabel} />
              <Stat name="Leaders" value={data.leader_count} detail="RVOL at or above 3×" />
              <Stat name="Watch" value={data.watch_count} detail={includeWatch ? '2× to below 3× included' : 'Counted, hidden from cards'} />
              <Stat name="Breadth" value={`${data.breadth.advances}:${data.breadth.declines}`} detail={`A/D ${data.breadth.advance_decline_ratio == null ? '—' : formatNumber(data.breadth.advance_decline_ratio)} · ${data.breadth.unchanged} flat`} />
              <Stat name="As of" value={formatTime(data.as_of).replace(' IST', '')} detail={`${formatDateTime(data.as_of)} · ${data.failures.length} failed`} />
            </section>

            <section className="ovl-results" aria-label="Opening volume signals">
              <div className="ovl-results-head">
                <h2>Ranked signals</h2>
                <small>{filtered.length} of {candidates.length} shown · tier → combo → quality → RVOL</small>
                <span className="ovl-filter-pills" aria-label="Direction filter">
                  {(['ALL', 'UP', 'DOWN'] as DirectionFilter[]).map((value) => (
                    <button key={value} type="button" data-on={direction === value} onClick={() => setDirection(value)}>{value}</button>
                  ))}
                </span>
                <select className="ovl-select" aria-label="Tier filter" value={tier} onChange={(event) => setTier(event.target.value as TierFilter)}>
                  {TIER_ORDER.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                </select>
                <input className="ovl-input" aria-label="Find symbol" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find symbol" />
              </div>

              {filtered.length > 0 ? (
                <div className="ovl-grid">
                  {filtered.map((signal) => (
                    <SignalCard key={signal.signal_key} signal={signal} rank={candidates.indexOf(signal) + 1} onOpenChart={onOpenChart} />
                  ))}
                </div>
              ) : (
                <section className="ovl-panel ovl-empty">
                  <h2>{candidates.length === 0 ? 'No opening-volume leaders found' : 'No signals match these filters'}</h2>
                  <p>{candidates.length === 0 ? 'The scan completed successfully, but no stock crossed the selected RVOL tier. Enable Watch to include 2–3× names.' : 'Clear the symbol, direction, or tier filter to see the scanned candidates.'}</p>
                </section>
              )}
            </section>

            {data.failures.length > 0 && (
              <details className="ovl-panel ovl-failures">
                <summary>{data.failures.length} symbol{data.failures.length === 1 ? '' : 's'} could not be evaluated</summary>
                <div className="ovl-failure-list">
                  {data.failures.map((failure) => <div key={failure.symbol} className="ovl-failure"><strong>{failure.symbol}</strong><span>{failure.error}</span></div>)}
                </div>
              </details>
            )}
          </>
        )}
      </div>
    </main>
  );
}

export default OpeningVolumeLeadersPane;
