import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  useOpeningVolumeContract,
  useOpeningExecutionConfig,
  useExecuteOpeningVolumeScan,
  useOpeningVolumeScan,
  useUpdateOpeningExecutionConfig,
  type OpeningVolumeScanRequest,
  type OpeningLeaderDirection,
  type OpeningLeaderSignal,
  type OpeningLeaderTier,
} from '../../hooks/useOpeningVolumeLeaders';
import { OPENING_VOLUME_LEADERS_CSS } from './openingVolumeLeadersCss';

type Scope = 'all' | 'custom';
type DirectionFilter = 'ALL' | OpeningLeaderDirection;
type TierFilter = 'all' | OpeningLeaderTier;

const TIER_ORDER: Array<{ id: TierFilter; label: string }> = [
  { id: 'all', label: 'All tiers' },
  { id: 'explosive', label: 'Explosive' },
  { id: 'strong', label: 'Strong' },
  { id: 'spurt', label: 'Spurt' },
  { id: 'watch', label: 'Watch' },
  { id: 'weak', label: 'Weak' },
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
  const minDigits = Number.isInteger(value) ? 0 : digits;
  return value.toLocaleString('en-IN', { minimumFractionDigits: minDigits, maximumFractionDigits: digits });
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

function followThroughLabel(signal: OpeningLeaderSignal): string {
  if (signal.move_1pct_within_60m === true) return '+1% hit ' + formatTime(signal.move_1pct_time);
  if (signal.move_1pct_within_60m === false) return '+1% not reached in 60m';
  return '+1% / 60m pending';
}

function RiskPlan({ signal, capital }: { signal: OpeningLeaderSignal; capital: number }) {
  const riskPct = signal.playbook.recommended_risk_pct;
  const riskAmount = capital * riskPct / 100;
  const reference = signal.orb_break_level;
  const stop = signal.protective_stop_price;
  const perShareRisk = reference != null && stop != null ? Math.abs(reference - stop) : 0;
  const quantity = perShareRisk > 0 ? Math.floor(riskAmount / perShareRisk) : 0;
  const probe = Math.floor(quantity * 0.30);
  const add = Math.floor(quantity * 0.30);
  const complete = Math.max(0, quantity - probe - add);
  const option = signal.option;
  const optionFitsBudget = option != null && option.lot_cost <= riskAmount;

  return (
    <div className="ovl-plan">
      <div className="ovl-plan-head">
        <strong>Documented risk plan</strong>
        <span>{formatNumber(riskPct, 1)}% · ₹{formatCompact(riskAmount)} risk</span>
      </div>
      <div className="ovl-detail-grid">
        <div><span>Reference</span><strong>{reference == null ? 'Await ORB' : '₹' + formatNumber(reference)}</strong></div>
        <div><span>Protective stop</span><strong>{stop == null ? '—' : '₹' + formatNumber(stop)}</strong></div>
        <div><span>Equity quantity</span><strong>{quantity || '—'}</strong></div>
        <div><span>30% probe</span><strong>{probe || '—'}</strong></div>
        <div><span>30% add</span><strong>{add || '—'}</strong></div>
        <div><span>40% complete</span><strong>{complete || '—'}</strong></div>
      </div>
      <p>Book ⅓–½ near 1.5R–2R, move stop to entry after the first scale, trail structure; stop after 2R/day or 4R/week.</p>
      {option && (
        <div className="ovl-option" data-warning={option.beginner_expiry_warning || !optionFitsBudget}>
          <div>
            <span>Nearest directional option</span>
            <strong>{option.tradingsymbol}</strong>
            <small>{option.option_type} · {formatNumber(option.strike, 0)} · {option.expiry} · DTE {option.dte}</small>
          </div>
          <div>
            <span>Premium / lot cost</span>
            <strong>₹{formatNumber(option.ltp)} / ₹{formatCompact(option.lot_cost)}</strong>
            <small>30% stop ₹{formatNumber(option.premium_stop_price)} · risk/lot ₹{formatCompact(option.premium_risk_per_lot)} · +50% target ₹{formatNumber(option.premium_target_price)}</small>
          </div>
          {(option.beginner_expiry_warning || !optionFitsBudget) && (
            <p>{option.beginner_expiry_warning ? 'Beginner rule: skip expiry day and the day before. ' : ''}{!optionFitsBudget ? 'One lot exceeds this card’s risk budget.' : ''}</p>
          )}
        </div>
      )}
      {!option && <p>Option quote: {label(signal.option_status)}.</p>}
    </div>
  );
}

function SignalCard({
  signal,
  rank,
  capital,
  onOpenChart,
}: {
  signal: OpeningLeaderSignal;
  rank: number;
  capital: number;
  onOpenChart?: (symbol: string) => void;
}) {
  const shownPrice = signal.live_price ?? signal.current_price;
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
        {signal.combo && <span className="ovl-badge" data-combo="true">COMBO</span>}
        {signal.decision.execution_eligible && <span className="ovl-badge" data-combo="true">Execution ready</span>}
        <span className="ovl-badge" data-combo={signal.decision.score.trade ? 'true' : undefined}>Score {formatNumber(signal.decision.score.lower_bound, 0)}–{formatNumber(signal.decision.score.upper_bound, 0)}</span>
        <span className="ovl-badge">Conviction {signal.decision.conviction.passed}/7</span>
        <span className="ovl-badge" data-combo={signal.decision.momentum.box_y ? 'true' : undefined}>Box {signal.decision.momentum.box_y ? 'Y' : signal.decision.momentum.box_x ? 'X' : '—'}</span>
        <span className="ovl-badge" data-gate={signal.playbook.known_gate_status}>{label(signal.playbook.known_gate_status)}</span>
        {signal.orb_fresh && <span className="ovl-badge" data-combo="true">Fresh ORB</span>}
        {signal.chase_state === 'chase' && <span className="ovl-badge" data-warning="true">Chase &gt;1%</span>}
        {signal.rally_aligned && <span className="ovl-badge">Rally ±2%</span>}
        {signal.third_day_repeat === true && <span className="ovl-badge" data-warning="true">3rd-day repeat</span>}
      </div>

      <div className="ovl-tape">
        <div>
          <span>{signal.live_price == null ? 'Last minute' : 'Live price'}</span>
          <strong>₹{formatNumber(shownPrice)}</strong>
        </div>
        <div>
          <span>ORB distance</span>
          <strong data-tone={signal.chase_state === 'chase' ? 'down' : undefined}>{formatPct(signal.orb_distance_pct)}</strong>
        </div>
        <div>
          <span>Stop distance</span>
          <strong data-tone={signal.stop_too_wide ? 'down' : undefined}>{signal.stop_distance_pct == null ? '—' : formatNumber(signal.stop_distance_pct) + '%'}</strong>
        </div>
      </div>

      <div className="ovl-evidence">
        <div className="ovl-event">
          <span>Actionable signal</span>
          <strong>{formatTime(signal.actionable_signal_time)} <em>· first ORB breach</em></strong>
        </div>
        <div className="ovl-event">
          <span>Volume signal</span>
          <strong>{formatTime(signal.volume_signal_time)} <em>· {formatCompact(signal.opening_volume)} vs {formatCompact(signal.average_opening_volume)} avg · {signal.baseline_session_count} sessions</em></strong>
        </div>
        <div className="ovl-event">
          <span>ORB</span>
          <strong>{formatTime(signal.orb_break_time)} <em>· {orbSide}{signal.orb_age_minutes != null ? ` · ${signal.orb_age_minutes}m ago` : ''}{signal.orb_cumulative_volume != null ? ` · ${formatCompact(signal.orb_cumulative_volume)} vol` : ''}</em></strong>
        </div>
        <div className="ovl-event">
          <span>Validation</span>
          <strong>5m hold {label(signal.hold_5m_status)} <em>· {followThroughLabel(signal)}</em></strong>
        </div>
        <div className="ovl-event">
          <span>Context</span>
          <strong>{label(signal.playbook.breadth_alignment)} breadth <em>· {label(signal.chase_state)} · {moveLabel} {formatPct(moveValue)}</em></strong>
        </div>
      </div>

      <div className="ovl-card-foot">
        <span className="ovl-state" data-state={signal.liquidity_state} title={liquidityTitle}><i />Liquidity {signal.liquidity_state}</span>
        {onOpenChart && <button type="button" className="ovl-chart" onClick={() => onOpenChart(signal.symbol)}>Chart</button>}
        <span className="ovl-quality">{signal.candle_quality} candle · {formatPct(signal.day_change_pct)} day · {label(signal.entry_phase)}</span>
      </div>

      <details className="ovl-details">
        <summary>War room · evidence, gates, option &amp; risk</summary>
        <div className="ovl-detail-grid">
          <div><span>Open</span><strong>₹{formatNumber(signal.opening_open)}</strong></div>
          <div><span>High</span><strong>₹{formatNumber(signal.opening_high)}</strong></div>
          <div><span>Low</span><strong>₹{formatNumber(signal.opening_low)}</strong></div>
          <div><span>Close</span><strong>₹{formatNumber(signal.opening_close)}</strong></div>
          <div><span>Day high / low</span><strong>{formatNumber(signal.session_high)} / {formatNumber(signal.session_low)}</strong></div>
          <div><span>Gap</span><strong>{formatPct(signal.gap_pct)}</strong></div>
          <div><span>Body / range</span><strong>{formatNumber(signal.body_pct)}% / {formatNumber(signal.range_pct)}%</strong></div>
          <div><span>Body fraction</span><strong>{formatNumber(signal.body_fraction * 100, 1)}%</strong></div>
          <div><span>Close location</span><strong>{formatNumber(signal.close_location * 100, 1)}%</strong></div>
          <div><span>Avg turnover</span><strong>{formatTurnover(signal.average_turnover_inr)}</strong></div>
          <div><span>VWAP</span><strong>{signal.intraday_vwap == null ? '—' : '₹' + formatNumber(signal.intraday_vwap)} · {signal.vwap_aligned == null ? 'unknown' : signal.vwap_aligned ? 'aligned' : 'against'}</strong></div>
          <div><span>PDH / PDL</span><strong>{formatNumber(signal.previous_day_high)} / {formatNumber(signal.previous_day_low)}</strong></div>
          <div><span>PDH/PDL break</span><strong>{signal.pdh_pdl_break_aligned == null ? 'Unknown' : signal.pdh_pdl_break_aligned ? 'Aligned' : 'Not aligned'}</strong></div>
          <div><span>RSI 14 · 1m</span><strong>{formatNumber(signal.rsi_14_1m, 1)}</strong></div>
          <div><span>50 DMA trend</span><strong>{signal.market_context.sma_50 == null ? '—' : '₹' + formatNumber(signal.market_context.sma_50)} · {signal.market_context.trend_50dma_aligned == null ? 'unknown' : signal.market_context.trend_50dma_aligned ? 'aligned' : 'against'}</strong></div>
          <div><span>52-week range</span><strong>{formatNumber(signal.market_context.low_52w ?? null)} – {formatNumber(signal.market_context.high_52w ?? null)}</strong></div>
          <div><span>From 52W high</span><strong>{formatPct(signal.market_context.distance_from_52w_high_pct ?? null)}</strong></div>
          <div><span>Daily context</span><strong>{label(signal.market_context.status)}</strong></div>
          <div><span>Repeat day</span><strong>{signal.consecutive_leader_days == null ? 'Unknown' : 'Day ' + signal.consecutive_leader_days}</strong></div>
          <div><span>Sterling score</span><strong>{formatNumber(signal.decision.score.lower_bound, 0)}–{formatNumber(signal.decision.score.upper_bound, 0)} · {formatNumber(signal.decision.score.coverage_pct, 0)}% evidence</strong></div>
          <div><span>Conviction</span><strong>{signal.decision.conviction.passed}/7 passed · {signal.decision.conviction.known}/7 known</strong></div>
          <div><span>Momentum</span><strong>Box X {signal.decision.momentum.box_x ? 'PASS' : 'FAIL'} · Box Y {signal.decision.momentum.box_y ? 'PASS' : 'FAIL'}</strong></div>
          {signal.liquidity_reasons.length > 0 && <div className="ovl-reason">{signal.liquidity_reasons.join(' · ')}</div>}
        </div>
        <details className="ovl-details">
          <summary>Score formula · earned / possible points</summary>
          <div className="ovl-detail-grid">
            {signal.decision.score.components.map((component) => (
              <div key={component.name}>
                <span>{label(component.name)}</span>
                <strong>
                  {formatNumber(component.earned, 1)} / {formatNumber(component.weight, 1)}
                  {' · '}{component.status}
                </strong>
              </div>
            ))}
          </div>
        </details>
        {(signal.playbook.known_gate_blockers.length > 0 || signal.playbook.known_gate_cautions.length > 0) && (
          <div className="ovl-gates">
            {signal.playbook.known_gate_blockers.map((item) => <p key={item} data-kind="block">Block · {item}</p>)}
            {signal.playbook.known_gate_cautions.map((item) => <p key={item} data-kind="caution">Caution · {item}</p>)}
          </div>
        )}
        <RiskPlan signal={signal} capital={capital} />
        <p className="ovl-private">{signal.decision.provenance}. ORION-private fields remain unverified: {signal.playbook.unverified_private_gates.join(' · ')}.</p>
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
  const executionConfigQuery = useOpeningExecutionConfig();
  const updateExecutionConfig = useUpdateOpeningExecutionConfig();
  const executeScan = useExecuteOpeningVolumeScan();
  const [scope, setScope] = useState<Scope>('all');
  const [symbolsText, setSymbolsText] = useState('');
  const [includeWatch, setIncludeWatch] = useState(false);
  const [includeWeak, setIncludeWeak] = useState(false);
  const [maxCandidates, setMaxCandidates] = useState(250);
  const [formError, setFormError] = useState<string | null>(null);
  const [direction, setDirection] = useState<DirectionFilter>('ALL');
  const [tier, setTier] = useState<TierFilter>('all');
  const [search, setSearch] = useState('');
  const [capital, setCapital] = useState(100_000);
  const [replayMode, setReplayMode] = useState(false);
  const [replayAt, setReplayAt] = useState('');
  const [autoScan, setAutoScan] = useState(false);
  const [autoMinutes, setAutoMinutes] = useState(5);

  const runScan = useCallback(() => {
    if (scan.isPending) return;
    const symbols = parseSymbols(symbolsText);
    if (scope === 'custom' && symbols.length === 0) {
      setFormError('Enter at least one current F&O equity symbol.');
      return;
    }
    if (replayMode && !replayAt) {
      setFormError('Choose an IST replay date and time.');
      return;
    }
    setFormError(null);
    scan.mutate({
      symbols: scope === 'custom' ? symbols : [],
      scan_all_stocks: scope === 'all',
      include_watch: includeWatch,
      include_weak: includeWeak,
      max_candidates: maxCandidates,
      concurrency: 3,
      history_calendar_days: 45,
      ...(replayMode ? { as_of: replayAt + (replayAt.length === 16 ? ':00+05:30' : '+05:30') } : {}),
      config: {},
    });
  }, [includeWatch, includeWeak, maxCandidates, replayAt, replayMode, scan.isPending, scan.mutate, scope, symbolsText]);

  const data = scan.data;
  useEffect(() => {
    if (!autoScan || replayMode || !data) return undefined;
    const timer = window.setInterval(runScan, autoMinutes * 60_000);
    return () => window.clearInterval(timer);
  }, [autoMinutes, autoScan, data, replayMode, runScan]);
  const candidates = useMemo(
    () => data ? [...data.leaders, ...data.watch, ...data.weak] : [],
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
  const executionConfig = updateExecutionConfig.data?.config ?? executionConfigQuery.data?.config;

  const executionRequest = (): OpeningVolumeScanRequest => ({
    symbols: scope === 'custom' ? parseSymbols(symbolsText) : [],
    scan_all_stocks: scope === 'all',
    include_watch: false,
    include_weak: false,
    max_candidates: maxCandidates,
    concurrency: 3,
    history_calendar_days: 45,
    config: {},
  });

  return (
    <main className="ovl-root">
      <style>{OPENING_VOLUME_LEADERS_CSS}</style>
      <div className="ovl-shell">
        <header className="ovl-header">
          <div>
            <p className="ovl-eyebrow">Opening volume · 1-minute cash candles</p>
            <h1 className="ovl-title">Opening Leaders</h1>
            <p className="ovl-subtitle">Find F&amp;O stocks whose completed 09:15 volume is abnormal versus the prior 10 matching opens, then validate breadth, freshness, chase distance, follow-through, liquidity, the nearest option, and documented risk limits.</p>
            <div className="ovl-contract" aria-label="Strategy contract">
              <span><strong>{version ? `Contract v${version}` : 'Loading contract'}</strong></span>
              <span>SPURT 3× · STRONG 5× · EXPLOSIVE 10×</span>
              <span>Transparent bounded Sterling score</span>
              {contractError && <span title={contractError}>Contract metadata unavailable</span>}
            </div>
          </div>
          <span className="ovl-advisory" title="Orders remain controlled by the shared Kite auto-execute switch. Paper/live follows the connected Kite account."><i />{executionConfig?.enabled ? 'Strategy enabled' : 'Strategy disabled'}</span>
        </header>

        <section className="ovl-panel" aria-label="Opening leader execution controls">
          <div className="ovl-toolbar">
            <div className="ovl-control">
              <span>Guarded execution</span>
              <strong>{executionConfig?.enabled ? 'Enabled' : 'Disabled'}</strong>
            </div>
            <label className="ovl-check">
              <input
                type="checkbox"
                aria-label="Enable Opening Leaders automatic execution"
                checked={executionConfig?.enabled ?? false}
                disabled={!executionConfig || updateExecutionConfig.isPending}
                onChange={(event) => updateExecutionConfig.mutate({ enabled: event.target.checked })}
              />
              Allow shared Kite auto-execute to trade risk-approved signals
            </label>
            <label className="ovl-control">
              <span>Minimum score</span>
              <select
                aria-label="Opening Leaders minimum execution score"
                className="ovl-select"
                value={executionConfig?.min_score ?? 55}
                disabled={!executionConfig || updateExecutionConfig.isPending}
                onChange={(event) => updateExecutionConfig.mutate({ min_score: Number(event.target.value) })}
              >
                {[55, 65, 75].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="ovl-control">
              <span>Conviction</span>
              <select
                aria-label="Opening Leaders minimum conviction"
                className="ovl-select"
                value={executionConfig?.min_conviction ?? 5}
                disabled={!executionConfig || updateExecutionConfig.isPending}
                onChange={(event) => updateExecutionConfig.mutate({ min_conviction: Number(event.target.value) })}
              >
                {[5, 6, 7].map((value) => <option key={value} value={value}>{value}/7</option>)}
              </select>
            </label>
            <label className="ovl-control">
              <span>Risk / trade</span>
              <select
                aria-label="Opening Leaders risk per trade"
                className="ovl-select"
                value={executionConfig?.risk_pct ?? 1}
                disabled={!executionConfig || updateExecutionConfig.isPending}
                onChange={(event) => updateExecutionConfig.mutate({ risk_pct: Number(event.target.value) })}
              >
                {[0.5, 1].map((value) => <option key={value} value={value}>{value}%</option>)}
              </select>
            </label>
            <label className="ovl-control">
              <span>Daily limit</span>
              <select
                aria-label="Opening Leaders daily trade limit"
                className="ovl-select"
                value={executionConfig?.max_trades_per_day ?? 2}
                disabled={!executionConfig || updateExecutionConfig.isPending}
                onChange={(event) => updateExecutionConfig.mutate({ max_trades_per_day: Number(event.target.value) })}
              >
                {[1, 2].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <button
              type="button"
              className="ovl-scan"
              disabled={!executionConfig?.enabled || executeScan.isPending || replayMode || (scope === 'custom' && parseSymbols(symbolsText).length === 0)}
              onClick={() => executeScan.mutate(executionRequest())}
            >
              {executeScan.isPending ? 'Validating & executing…' : 'Execute eligible now'}
            </button>
          </div>
          <p className="ovl-private">Requires Kite auto-execute on, score ≥{executionConfig?.min_score ?? 55}, conviction ≥{executionConfig?.min_conviction ?? 5}/7, fresh Box Y, a non-expiry contract, a fresh executable quote, affordable risk size, and successful stop/target protection. Paper/live follows the connected Kite account.</p>
          {executeScan.data && <p className="ovl-private">Last execution: {label(executeScan.data.execution.status)}{executeScan.data.execution.reason ? ` · ${executeScan.data.execution.reason}` : ''}</p>}
          {executeScan.error && <p role="alert" className="ovl-form-error">Execution failed: {executeScan.error.message}</p>}
        </section>

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
            <label className="ovl-check">
              <input type="checkbox" checked={includeWeak} onChange={(event) => setIncludeWeak(event.target.checked)} />
              Include below 2×
            </label>
            <label className="ovl-check">
              <input type="checkbox" checked={replayMode} onChange={(event) => setReplayMode(event.target.checked)} />
              Replay
            </label>
            <label className="ovl-check">
              <input type="checkbox" checked={autoScan} disabled={replayMode} onChange={(event) => setAutoScan(event.target.checked)} />
              Auto
            </label>
            {autoScan && !replayMode && (
              <label className="ovl-control">
                <span>Every</span>
                <select className="ovl-select" aria-label="Auto scan interval" value={autoMinutes} onChange={(event) => setAutoMinutes(Number(event.target.value))}>
                  {[1, 5, 10].map((minutes) => <option key={minutes} value={minutes}>{minutes} min</option>)}
                </select>
              </label>
            )}
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
          <div className="ovl-scope-input ovl-secondary-controls">
            {replayMode && (
              <label className="ovl-control">
                <span>Replay as of · IST</span>
                <input className="ovl-input" aria-label="Replay as of" type="datetime-local" value={replayAt} onChange={(event) => setReplayAt(event.target.value)} />
              </label>
            )}
            <label className="ovl-control">
              <span>Capital for risk plan · INR</span>
              <input className="ovl-input" aria-label="Risk-plan capital" type="number" min={1000} step={1000} value={capital} onChange={(event) => setCapital(Math.max(0, Number(event.target.value)))} />
            </label>
            <small>{autoScan && data && !replayMode ? 'Auto refresh every ' + autoMinutes + ' minutes after this completed scan.' : 'Auto refresh starts only after the first manual scan.'}</small>
          </div>
          {formError && <p role="alert" className="ovl-form-error">{formError}</p>}
        </section>

        {scan.isPending && (
          <section className="ovl-panel ovl-progress" aria-live="polite">
            <span className="ovl-spinner" />
            <strong>Reading the opening candle history</strong>
            <p>The full-universe scan is broker-rate-limited and can take about 1–2 minutes. Scanning never places an order; only the separate guarded execution control can submit an eligible signal when shared Kite auto-execute is on.</p>
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
              <Stat name="ORB events" value={data.event_count} detail={`${data.pending_orb_count} stocks have not broken the 09:15 range`} />
              <Stat name="Leader / lower" value={data.leader_count + ' / ' + (data.watch_count + data.weak_count)} detail={(includeWatch || includeWeak) ? 'Selected event tiers included' : 'Lower-tier events counted, hidden'} />
              <Stat name="Breadth" value={`${data.breadth.advances}:${data.breadth.declines}`} detail={`A/D ${data.breadth.advance_decline_ratio == null ? '—' : formatNumber(data.breadth.advance_decline_ratio)} · ${data.breadth.unchanged} flat`} />
              <Stat name="As of" value={formatTime(data.as_of).replace(' IST', '')} detail={`${formatDateTime(data.as_of)} · ${data.failures.length} failed`} />
            </section>

            <section className="ovl-panel ovl-breadth" data-mood={data.breadth.mood} aria-label="Market breadth gate">
              <div>
                <span>Market breadth</span>
                <strong>{label(data.breadth.mood)}</strong>
              </div>
              <p>{formatNumber(data.breadth.green_pct, 1)}% advancing · {label(data.breadth.participation)} participation · {formatNumber(data.breadth.coverage_pct, 1)}% universe coverage. Aligned signals use the 1% idea-risk ceiling; neutral breadth halves it; counter-breadth setups are blocked.</p>
              <small>{data.breadth.mood_rule}</small>
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
                    <SignalCard key={signal.signal_key} signal={signal} rank={candidates.indexOf(signal) + 1} capital={capital} onOpenChart={onOpenChart} />
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
