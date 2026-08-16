import React, { useState, useMemo } from 'react';
import {
  useUnifiedStrategies,
  useUnifiedPresets,
  useRunUnifiedBacktest,
} from '../../hooks/useUnifiedBacktest';
import type {
  BacktestTrade,
  UnifiedBacktestRequest,
  UnifiedBacktestResult,
} from '../../types/backtest';
import { k } from '../../styles/kiteUI';

function fmt(n: number, dp = 2): string {
  if (!isFinite(n)) return '0.00';
  return n.toLocaleString('en-IN', { maximumFractionDigits: dp, minimumFractionDigits: dp });
}

function fmtCurr(n: number): string {
  if (!isFinite(n)) return '₹0.00';
  const prefix = n >= 0 ? '+₹' : '-₹';
  return `${prefix}${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;
}

export function UnifiedBacktestPane() {
  const { data: strategies = [] } = useUnifiedStrategies();
  const { data: presets = [] } = useUnifiedPresets();
  const runMutation = useRunUnifiedBacktest();

  // Form State
  const [strategy, setStrategy] = useState('adaptive_edge');
  const [symbol, setSymbol] = useState('NIFTY 50');
  const [timeframe, setTimeframe] = useState('5m');
  const [lookbackDays, setLookbackDays] = useState(30);
  const [startingCapital, setStartingCapital] = useState(100000);
  const [numLots, setNumLots] = useState(2);
  const [stopPoints, setStopPoints] = useState<number | undefined>(40);
  const [targetPoints, setTargetPoints] = useState<number | undefined>(80);
  const [trailPoints, setTrailPoints] = useState<number | undefined>(25);
  const [slippagePoints, setSlippagePoints] = useState(0.5);
  const [brokerage, setBrokerage] = useState(20.0);
  const [sttPct, setSttPct] = useState(0.00125);

  // View state
  const [activeTab, setActiveTab] = useState<'equity' | 'drawdown' | 'trades' | 'monte_carlo'>('equity');
  const [tradeFilter, setTradeFilter] = useState<'ALL' | 'WIN' | 'LOSS'>('ALL');
  const [result, setResult] = useState<UnifiedBacktestResult | null>(null);

  const handleApplyPreset = (p: typeof presets[0]) => {
    setStrategy(p.strategy);
    setSymbol(p.symbol);
    setTimeframe(p.timeframe);
    setLookbackDays(p.lookback_days);
    setStartingCapital(p.starting_capital);
    setNumLots(p.num_lots);
    setStopPoints(p.stop_points);
    setTargetPoints(p.target_points);
    setTrailPoints(p.trail_points);
    setSlippagePoints(p.slippage_points);
  };

  const handleRunBacktest = () => {
    const payload: UnifiedBacktestRequest = {
      strategy,
      symbol,
      timeframe,
      lookback_days: lookbackDays,
      starting_capital: startingCapital,
      num_lots: numLots,
      stop_points: stopPoints,
      target_points: targetPoints,
      trail_points: trailPoints,
      slippage_points: slippagePoints,
      brokerage_per_order: brokerage,
      stt_pct: sttPct,
      session_cutoff_hour: 15,
      session_cutoff_min: 15,
    };
    runMutation.mutate(payload, {
      onSuccess: (res) => {
        setResult(res);
      },
    });
  };

  const filteredTrades = useMemo(() => {
    if (!result?.trades) return [];
    if (tradeFilter === 'WIN') return result.trades.filter((t) => t.net_pnl > 0);
    if (tradeFilter === 'LOSS') return result.trades.filter((t) => t.net_pnl <= 0);
    return result.trades;
  }, [result, tradeFilter]);

  const handleExportCSV = () => {
    if (!result?.trades || result.trades.length === 0) return;
    const headers = [
      'Trade ID',
      'Entry Time',
      'Exit Time',
      'Direction',
      'Entry Price',
      'Exit Price',
      'Qty',
      'Gross PnL (INR)',
      'Friction (INR)',
      'Net PnL (INR)',
      'Return (%)',
      'MAE (pts)',
      'MFE (pts)',
      'Exit Reason',
    ];
    const rows = result.trades.map((t) => [
      t.trade_id,
      t.entry_time,
      t.exit_time,
      t.direction,
      t.entry_price,
      t.exit_price,
      t.qty,
      t.gross_pnl,
      t.friction_cost,
      t.net_pnl,
      t.return_pct,
      t.mae_points,
      t.mfe_points,
      t.exit_reason,
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `backtest_${result.strategy}_${result.symbol}_${result.timeframe}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', background: '#f5f5f5', overflow: 'hidden' }}>
      {/* ── Top Bar: Presets & Real Data Status ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 20px', background: '#fff', borderBottom: `1px solid ${k.border}`, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: '#666', textTransform: 'uppercase', letterSpacing: 0.5, marginRight: 4 }}>
            Presets:
          </span>
          {presets.map((p) => (
            <button
              key={p.name}
              onClick={() => handleApplyPreset(p)}
              style={{
                fontSize: 11.5, fontWeight: 500, padding: '4px 10px', borderRadius: 14,
                border: '1px solid #ddd', background: '#fafafa', color: '#444', cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#f06428'; e.currentTarget.style.color = '#f06428'; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#ddd'; e.currentTarget.style.color = '#444'; }}
            >
              {p.name}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, fontWeight: 600, color: '#2e7d32', background: 'rgba(46,125,50,0.08)', padding: '4px 10px', borderRadius: 4 }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#2e7d32' }} />
          REAL HISTORICAL DATA ENGINE
        </div>
      </div>

      {/* ── Main Content Area ── */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* ── Left Sidebar: Strategy & Parameters Config ── */}
        <div style={{ width: 320, background: '#fff', borderRight: `1px solid ${k.border}`, padding: '18px 20px', overflowY: 'auto', flexShrink: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#333', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
            ⚙️ Strategy & Engine Parameters
          </div>

          {/* Strategy Picker */}
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: '#777', textTransform: 'uppercase', marginBottom: 4 }}>
              Strategy
            </label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              style={{ width: '100%', padding: '7px 9px', fontSize: 13, borderRadius: 4, border: `1px solid ${k.border}`, background: '#fff' }}
            >
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>{s.name} ({s.category})</option>
              ))}
            </select>
          </div>

          {/* Instrument & Timeframe */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: '#777', textTransform: 'uppercase', marginBottom: 4 }}>
                Instrument
              </label>
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                style={{ width: '100%', padding: '7px 9px', fontSize: 13, borderRadius: 4, border: `1px solid ${k.border}`, background: '#fff' }}
              >
                <option value="NIFTY 50">NIFTY 50</option>
                <option value="NIFTY BANK">NIFTY BANK</option>
                <option value="NIFTY FIN SERVICE">FINNIFTY</option>
                <option value="SENSEX">SENSEX</option>
                <option value="RELIANCE">RELIANCE</option>
                <option value="HDFCBANK">HDFCBANK</option>
                <option value="INFY">INFY</option>
                <option value="TCS">TCS</option>
                <option value="BTCUSD">BTC/USD</option>
                <option value="ETHUSD">ETH/USD</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: '#777', textTransform: 'uppercase', marginBottom: 4 }}>
                Timeframe
              </label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                style={{ width: '100%', padding: '7px 9px', fontSize: 13, borderRadius: 4, border: `1px solid ${k.border}`, background: '#fff' }}
              >
                <option value="1m">1 Minute</option>
                <option value="3m">3 Minute</option>
                <option value="5m">5 Minute</option>
                <option value="15m">15 Minute</option>
                <option value="30m">30 Minute</option>
                <option value="1h">1 Hour</option>
                <option value="day">1 Day</option>
              </select>
            </div>
          </div>

          {/* Lookback Days & Starting Capital */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: '#777', textTransform: 'uppercase', marginBottom: 4 }}>
                Lookback (Days)
              </label>
              <input
                type="number"
                min={3}
                max={365}
                value={lookbackDays}
                onChange={(e) => setLookbackDays(Number(e.target.value))}
                style={{ width: '100%', padding: '7px 9px', fontSize: 13, borderRadius: 4, border: `1px solid ${k.border}`, background: '#fff', boxSizing: 'border-box' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: '#777', textTransform: 'uppercase', marginBottom: 4 }}>
                Lots
              </label>
              <input
                type="number"
                min={1}
                max={100}
                value={numLots}
                onChange={(e) => setNumLots(Number(e.target.value))}
                style={{ width: '100%', padding: '7px 9px', fontSize: 13, borderRadius: 4, border: `1px solid ${k.border}`, background: '#fff', boxSizing: 'border-box' }}
              />
            </div>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: '#777', textTransform: 'uppercase', marginBottom: 4 }}>
              Starting Capital (₹)
            </label>
            <input
              type="number"
              step={10000}
              value={startingCapital}
              onChange={(e) => setStartingCapital(Number(e.target.value))}
              style={{ width: '100%', padding: '7px 9px', fontSize: 13, borderRadius: 4, border: `1px solid ${k.border}`, background: '#fff', boxSizing: 'border-box' }}
            />
          </div>

          {/* Stop, Target & Trailing */}
          <div style={{ borderTop: `1px solid ${k.border}`, paddingTop: 12, marginBottom: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#444', marginBottom: 10 }}>
              🛡️ Risk & Exit Boundaries (Points)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              <div>
                <label style={{ display: 'block', fontSize: 10, fontWeight: 700, color: '#888', marginBottom: 2 }}>Stop (SL)</label>
                <input
                  type="number"
                  value={stopPoints ?? ''}
                  placeholder="Auto ATR"
                  onChange={(e) => setStopPoints(e.target.value ? Number(e.target.value) : undefined)}
                  style={{ width: '100%', padding: '6px 6px', fontSize: 12, borderRadius: 4, border: `1px solid ${k.border}`, boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 10, fontWeight: 700, color: '#888', marginBottom: 2 }}>Target (TP)</label>
                <input
                  type="number"
                  value={targetPoints ?? ''}
                  placeholder="Auto 2R"
                  onChange={(e) => setTargetPoints(e.target.value ? Number(e.target.value) : undefined)}
                  style={{ width: '100%', padding: '6px 6px', fontSize: 12, borderRadius: 4, border: `1px solid ${k.border}`, boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 10, fontWeight: 700, color: '#888', marginBottom: 2 }}>Trail (TSL)</label>
                <input
                  type="number"
                  value={trailPoints ?? ''}
                  placeholder="Disabled"
                  onChange={(e) => setTrailPoints(e.target.value ? Number(e.target.value) : undefined)}
                  style={{ width: '100%', padding: '6px 6px', fontSize: 12, borderRadius: 4, border: `1px solid ${k.border}`, boxSizing: 'border-box' }}
                />
              </div>
            </div>
          </div>

          {/* Friction & Costs */}
          <div style={{ borderTop: `1px solid ${k.border}`, paddingTop: 12, marginBottom: 18 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#444', marginBottom: 10 }}>
              💸 Indian F&O Friction Engine
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 8 }}>
              <div>
                <label style={{ display: 'block', fontSize: 10, fontWeight: 700, color: '#888', marginBottom: 2 }}>Slippage (pts)</label>
                <input
                  type="number"
                  step={0.1}
                  value={slippagePoints}
                  onChange={(e) => setSlippagePoints(Number(e.target.value))}
                  style={{ width: '100%', padding: '6px 8px', fontSize: 12, borderRadius: 4, border: `1px solid ${k.border}`, boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 10, fontWeight: 700, color: '#888', marginBottom: 2 }}>Brokerage (₹/ord)</label>
                <input
                  type="number"
                  value={brokerage}
                  onChange={(e) => setBrokerage(Number(e.target.value))}
                  style={{ width: '100%', padding: '6px 8px', fontSize: 12, borderRadius: 4, border: `1px solid ${k.border}`, boxSizing: 'border-box' }}
                />
              </div>
            </div>
            <div style={{ fontSize: 11, color: '#888', lineHeight: 1.4 }}>
              Includes STT (0.125%), Exchange Turnover (0.05%), and 18% GST on brokerage.
            </div>
          </div>

          {/* Run Button */}
          <button
            onClick={handleRunBacktest}
            disabled={runMutation.isPending}
            style={{
              width: '100%', padding: '12px', background: runMutation.isPending ? '#ccc' : '#f06428',
              color: '#fff', border: 'none', borderRadius: 4, fontSize: 14, fontWeight: 700,
              cursor: runMutation.isPending ? 'not-allowed' : 'pointer', transition: 'background 0.15s ease',
            }}
          >
            {runMutation.isPending ? 'Replaying Real Market Bars…' : '⚡ Run Backtest'}
          </button>
        </div>

        {/* ── Right Main Surface: Metrics, Charts, Trades, Monte Carlo ── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto', padding: 20 }}>
          {!result && !runMutation.isPending && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#888' }}>
              <div style={{ fontSize: 36, marginBottom: 12 }}>📊</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#444', marginBottom: 4 }}>
                Ready to Run Real-Data Backtest
              </div>
              <div style={{ fontSize: 13, maxWidth: 450, textAlign: 'center', lineHeight: 1.5 }}>
                Select a preset or customize your strategy parameters on the left, then click <strong>Run Backtest</strong> to evaluate performance on genuine historical candles.
              </div>
            </div>
          )}

          {runMutation.isPending && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#888' }}>
              <div style={{ fontSize: 32, marginBottom: 12, animation: 'spin 1s infinite linear' }}>⏳</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: '#333', marginBottom: 4 }}>
                Fetching Historical Candles & Simulating Executions…
              </div>
              <div style={{ fontSize: 12 }}>Calculating Black-Scholes greeks, fee ledgers, and MAE/MFE diagnostics</div>
            </div>
          )}

          {result && !runMutation.isPending && (
            <>
              {/* ── KPI Metric Scorecard ── */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 12, marginBottom: 18 }}>
                <div style={{ background: '#fff', padding: '12px 14px', borderRadius: 6, border: `1px solid ${k.border}` }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#888', textTransform: 'uppercase' }}>Net P&L</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: result.metrics.net_pnl_inr >= 0 ? '#2e7d32' : '#c62828', marginTop: 2 }}>
                    {fmtCurr(result.metrics.net_pnl_inr)}
                  </div>
                  <div style={{ fontSize: 11, color: result.metrics.total_return_pct >= 0 ? '#2e7d32' : '#c62828', fontWeight: 600 }}>
                    {result.metrics.total_return_pct >= 0 ? '+' : ''}{result.metrics.total_return_pct}%
                  </div>
                </div>

                <div style={{ background: '#fff', padding: '12px 14px', borderRadius: 6, border: `1px solid ${k.border}` }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#888', textTransform: 'uppercase' }}>Sharpe Ratio</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: result.metrics.sharpe_ratio >= 1.5 ? '#2e7d32' : '#333', marginTop: 2 }}>
                    {fmt(result.metrics.sharpe_ratio)}
                  </div>
                  <div style={{ fontSize: 11, color: '#888' }}>Sortino: {fmt(result.metrics.sortino_ratio)}</div>
                </div>

                <div style={{ background: '#fff', padding: '12px 14px', borderRadius: 6, border: `1px solid ${k.border}` }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#888', textTransform: 'uppercase' }}>Win Rate</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: result.metrics.win_rate_pct >= 50 ? '#2e7d32' : '#c62828', marginTop: 2 }}>
                    {result.metrics.win_rate_pct}%
                  </div>
                  <div style={{ fontSize: 11, color: '#888' }}>{result.metrics.winning_trades}W / {result.metrics.losing_trades}L</div>
                </div>

                <div style={{ background: '#fff', padding: '12px 14px', borderRadius: 6, border: `1px solid ${k.border}` }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#888', textTransform: 'uppercase' }}>Profit Factor</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: result.metrics.profit_factor >= 1.5 ? '#2e7d32' : '#333', marginTop: 2 }}>
                    {fmt(result.metrics.profit_factor)}
                  </div>
                  <div style={{ fontSize: 11, color: '#888' }}>Payoff: {fmt(result.metrics.payoff_ratio)}x</div>
                </div>

                <div style={{ background: '#fff', padding: '12px 14px', borderRadius: 6, border: `1px solid ${k.border}` }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#888', textTransform: 'uppercase' }}>Max Drawdown</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: result.metrics.max_drawdown_pct <= 5 ? '#2e7d32' : '#c62828', marginTop: 2 }}>
                    -{result.metrics.max_drawdown_pct}%
                  </div>
                  <div style={{ fontSize: 11, color: '#888' }}>{fmtCurr(-result.metrics.max_drawdown_inr)}</div>
                </div>

                <div style={{ background: '#fff', padding: '12px 14px', borderRadius: 6, border: `1px solid ${k.border}` }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#888', textTransform: 'uppercase' }}>Total Trades</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: '#333', marginTop: 2 }}>
                    {result.metrics.total_trades}
                  </div>
                  <div style={{ fontSize: 11, color: '#888' }}>Exp: {fmtCurr(result.metrics.expectancy_inr)}</div>
                </div>

                <div style={{ background: '#fff', padding: '12px 14px', borderRadius: 6, border: `1px solid ${k.border}` }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#888', textTransform: 'uppercase' }}>Friction / STT</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: '#888', marginTop: 2 }}>
                    ₹{fmt(result.metrics.total_friction_inr, 0)}
                  </div>
                  <div style={{ fontSize: 11, color: '#888' }}>Drag: {result.metrics.friction_drag_pct}%</div>
                </div>
              </div>

              {/* ── Visualization Navigation Tabs ── */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: `1px solid ${k.border}`, background: '#fff', borderRadius: '6px 6px 0 0', padding: '0 12px' }}>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[
                    { id: 'equity' as const, label: '📈 Equity Curve' },
                    { id: 'drawdown' as const, label: '🌊 Underwater Drawdown' },
                    { id: 'trades' as const, label: `📑 Trade Ledger (${result.trades.length})` },
                    { id: 'monte_carlo' as const, label: '🎲 Monte Carlo (500 Paths)' },
                  ].map((t) => {
                    const active = activeTab === t.id;
                    return (
                      <button
                        key={t.id}
                        onClick={() => setActiveTab(t.id)}
                        style={{
                          padding: '12px 16px', border: 'none', background: 'transparent', cursor: 'pointer',
                          fontSize: 13, fontWeight: active ? 700 : 500,
                          color: active ? '#f06428' : '#666',
                          borderBottom: active ? '2px solid #f06428' : '2px solid transparent',
                          marginBottom: -1,
                        }}
                      >
                        {t.label}
                      </button>
                    );
                  })}
                </div>

                {activeTab === 'trades' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ display: 'flex', gap: 4, background: '#eee', padding: 2, borderRadius: 4 }}>
                      {(['ALL', 'WIN', 'LOSS'] as const).map((mode) => (
                        <button
                          key={mode}
                          onClick={() => setTradeFilter(mode)}
                          style={{
                            border: 'none', padding: '3px 8px', fontSize: 11, fontWeight: 700, borderRadius: 3,
                            background: tradeFilter === mode ? '#fff' : 'transparent',
                            color: tradeFilter === mode ? '#333' : '#777', cursor: 'pointer',
                          }}
                        >
                          {mode}
                        </button>
                      ))}
                    </div>
                    <button
                      onClick={handleExportCSV}
                      style={{
                        padding: '5px 12px', background: '#f5f5f5', border: `1px solid ${k.border}`,
                        borderRadius: 4, fontSize: 12, fontWeight: 600, color: '#333', cursor: 'pointer',
                      }}
                    >
                      📥 Export CSV
                    </button>
                  </div>
                )}
              </div>

              {/* ── Tab Views ── */}
              <div style={{ background: '#fff', border: `1px solid ${k.border}`, borderTop: 'none', borderRadius: '0 0 6px 6px', padding: 20, flex: 1, minHeight: 380, overflowY: 'auto' }}>
                {activeTab === 'equity' && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: '#444' }}>
                        Portfolio Capital Growth vs. High-Water Mark (INR)
                      </span>
                      <span style={{ fontSize: 12, color: '#888' }}>
                        Evaluated {result.candles_evaluated} real candles ({result.start_date.substring(0, 10)} → {result.end_date.substring(0, 10)})
                      </span>
                    </div>

                    {/* SVG Equity Chart */}
                    <div style={{ width: '100%', height: 320, background: '#fafafa', borderRadius: 4, border: '1px solid #eee', padding: 10, position: 'relative' }}>
                      <svg width="100%" height="100%" viewBox="0 0 800 280" preserveAspectRatio="none">
                        {(() => {
                          const pts = result.equity_curve;
                          if (pts.length < 2) return null;
                          const values = pts.map((p) => p.equity);
                          const min = Math.min(...values) * 0.98;
                          const max = Math.max(...values, result.starting_capital) * 1.02;
                          const span = max - min || 1;

                          const coords = pts.map((p, i) => {
                            const x = (i / (pts.length - 1)) * 780 + 10;
                            const y = 260 - ((p.equity - min) / span) * 240;
                            return `${x.toFixed(1)},${y.toFixed(1)}`;
                          });

                          const hwmCoords = pts.map((p, i) => {
                            const x = (i / (pts.length - 1)) * 780 + 10;
                            const y = 260 - ((p.high_water_mark - min) / span) * 240;
                            return `${x.toFixed(1)},${y.toFixed(1)}`;
                          });

                          const polyline = coords.join(' ');
                          const area = `10,260 ${polyline} 790,260`;
                          const isUp = values[values.length - 1] >= values[0];

                          return (
                            <>
                              {/* Baseline Capital Line */}
                              <line
                                x1="10"
                                y1={260 - ((result.starting_capital - min) / span) * 240}
                                x2="790"
                                y2={260 - ((result.starting_capital - min) / span) * 240}
                                stroke="#ccc"
                                strokeDasharray="4 4"
                                strokeWidth="1"
                              />
                              {/* Area fill */}
                              <polygon points={area} fill={isUp ? 'rgba(46,125,50,0.08)' : 'rgba(198,40,40,0.08)'} />
                              {/* HWM Line */}
                              <polyline points={hwmCoords.join(' ')} fill="none" stroke="#90caf9" strokeDasharray="3 3" strokeWidth="1.5" />
                              {/* Equity Line */}
                              <polyline points={polyline} fill="none" stroke={isUp ? '#2e7d32' : '#c62828'} strokeWidth="2.5" />
                            </>
                          );
                        })()}
                      </svg>
                    </div>
                  </div>
                )}

                {activeTab === 'drawdown' && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: '#444' }}>
                        Underwater Drawdown Profile (%)
                      </span>
                      <span style={{ fontSize: 12, color: '#c62828', fontWeight: 600 }}>
                        Maximum Drawdown: -{result.metrics.max_drawdown_pct}%
                      </span>
                    </div>

                    <div style={{ width: '100%', height: 320, background: '#fafafa', borderRadius: 4, border: '1px solid #eee', padding: 10 }}>
                      <svg width="100%" height="100%" viewBox="0 0 800 280" preserveAspectRatio="none">
                        {(() => {
                          const pts = result.equity_curve;
                          if (pts.length < 2) return null;
                          const maxDd = Math.max(...pts.map((p) => p.drawdown_pct), 5);

                          const coords = pts.map((p, i) => {
                            const x = (i / (pts.length - 1)) * 780 + 10;
                            const y = 20 + (p.drawdown_pct / maxDd) * 240;
                            return `${x.toFixed(1)},${y.toFixed(1)}`;
                          });

                          const area = `10,20 ${coords.join(' ')} 790,20`;
                          return (
                            <>
                              <line x1="10" y1="20" x2="790" y2="20" stroke="#aaa" strokeWidth="1.5" />
                              <polygon points={area} fill="rgba(229,57,53,0.2)" />
                              <polyline points={coords.join(' ')} fill="none" stroke="#e53935" strokeWidth="2" />
                            </>
                          );
                        })()}
                      </svg>
                    </div>
                  </div>
                )}

                {activeTab === 'trades' && (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                      <thead>
                        <tr style={{ background: '#f8f9fa', borderBottom: `2px solid ${k.border}`, color: '#666' }}>
                          <th style={{ padding: '8px 10px' }}>#</th>
                          <th style={{ padding: '8px 10px' }}>Entry Time</th>
                          <th style={{ padding: '8px 10px' }}>Exit Time</th>
                          <th style={{ padding: '8px 10px' }}>Side</th>
                          <th style={{ padding: '8px 10px' }}>Entry</th>
                          <th style={{ padding: '8px 10px' }}>Exit</th>
                          <th style={{ padding: '8px 10px' }}>Gross P&L</th>
                          <th style={{ padding: '8px 10px' }}>Friction</th>
                          <th style={{ padding: '8px 10px' }}>Net P&L</th>
                          <th style={{ padding: '8px 10px' }}>MAE / MFE</th>
                          <th style={{ padding: '8px 10px' }}>Exit Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredTrades.map((t) => {
                          const isWin = t.net_pnl > 0;
                          return (
                            <tr key={t.trade_id} style={{ borderBottom: '1px solid #eee' }}>
                              <td style={{ padding: '8px 10px', color: '#888' }}>{t.trade_id}</td>
                              <td style={{ padding: '8px 10px' }}>{t.entry_time.replace('T', ' ').substring(5, 16)}</td>
                              <td style={{ padding: '8px 10px' }}>{t.exit_time.replace('T', ' ').substring(5, 16)}</td>
                              <td style={{ padding: '8px 10px', fontWeight: 700, color: t.direction === 'LONG' ? '#2e7d32' : '#c62828' }}>
                                {t.direction}
                              </td>
                              <td style={{ padding: '8px 10px' }}>₹{t.entry_price}</td>
                              <td style={{ padding: '8px 10px' }}>₹{t.exit_price}</td>
                              <td style={{ padding: '8px 10px', color: t.gross_pnl >= 0 ? '#2e7d32' : '#c62828' }}>
                                {fmtCurr(t.gross_pnl)}
                              </td>
                              <td style={{ padding: '8px 10px', color: '#888' }}>₹{t.friction_cost}</td>
                              <td style={{ padding: '8px 10px', fontWeight: 700, color: isWin ? '#2e7d32' : '#c62828' }}>
                                {fmtCurr(t.net_pnl)} ({t.return_pct}%)
                              </td>
                              <td style={{ padding: '8px 10px', color: '#666', fontSize: 11 }}>
                                -{t.mae_points} / +{t.mfe_points} pts
                              </td>
                              <td style={{ padding: '8px 10px' }}>
                                <span style={{
                                  fontSize: 10.5, fontWeight: 700, padding: '2px 6px', borderRadius: 3,
                                  background: t.exit_reason === 'TARGET' ? 'rgba(46,125,50,0.12)' : (t.exit_reason === 'STOP_LOSS' ? 'rgba(198,40,40,0.12)' : '#eee'),
                                  color: t.exit_reason === 'TARGET' ? '#2e7d32' : (t.exit_reason === 'STOP_LOSS' ? '#c62828' : '#555'),
                                }}>
                                  {t.exit_reason}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {activeTab === 'monte_carlo' && (
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#333', marginBottom: 6 }}>
                      🎲 500-Path Monte Carlo Resampling Simulation
                    </div>
                    <div style={{ fontSize: 12, color: '#777', marginBottom: 16 }}>
                      Randomizes trade sequencing 500 times to compute statistical confidence bounds and evaluate drawdowns under unfavorable streak orderings.
                    </div>

                    {result.monte_carlo ? (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14 }}>
                        <div style={{ background: '#fafafa', padding: 14, borderRadius: 6, border: '1px solid #eee' }}>
                          <div style={{ fontSize: 11, color: '#888', textTransform: 'uppercase', fontWeight: 700 }}>Mean Expected Return</div>
                          <div style={{ fontSize: 20, fontWeight: 800, color: result.monte_carlo.mean_return_pct >= 0 ? '#2e7d32' : '#c62828', marginTop: 4 }}>
                            {result.monte_carlo.mean_return_pct}%
                          </div>
                        </div>

                        <div style={{ background: '#fafafa', padding: 14, borderRadius: 6, border: '1px solid #eee' }}>
                          <div style={{ fontSize: 11, color: '#888', textTransform: 'uppercase', fontWeight: 700 }}>5th Percentile (Worst 5%)</div>
                          <div style={{ fontSize: 20, fontWeight: 800, color: '#c62828', marginTop: 4 }}>
                            {result.monte_carlo.p5_return_pct}%
                          </div>
                        </div>

                        <div style={{ background: '#fafafa', padding: 14, borderRadius: 6, border: '1px solid #eee' }}>
                          <div style={{ fontSize: 11, color: '#888', textTransform: 'uppercase', fontWeight: 700 }}>95th Percentile (Best 5%)</div>
                          <div style={{ fontSize: 20, fontWeight: 800, color: '#2e7d32', marginTop: 4 }}>
                            +{result.monte_carlo.p95_return_pct}%
                          </div>
                        </div>

                        <div style={{ background: '#fafafa', padding: 14, borderRadius: 6, border: '1px solid #eee' }}>
                          <div style={{ fontSize: 11, color: '#888', textTransform: 'uppercase', fontWeight: 700 }}>95% Max Drawdown Risk</div>
                          <div style={{ fontSize: 20, fontWeight: 800, color: '#c62828', marginTop: 4 }}>
                            -{result.monte_carlo.p95_max_drawdown_pct}%
                          </div>
                        </div>

                        <div style={{ background: '#fafafa', padding: 14, borderRadius: 6, border: '1px solid #eee' }}>
                          <div style={{ fontSize: 11, color: '#888', textTransform: 'uppercase', fontWeight: 700 }}>Probability of Profit</div>
                          <div style={{ fontSize: 20, fontWeight: 800, color: result.monte_carlo.prob_profit_pct >= 70 ? '#2e7d32' : '#f06428', marginTop: 4 }}>
                            {result.monte_carlo.prob_profit_pct}%
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ color: '#888', fontSize: 13 }}>
                        Requires at least 5 completed trades to run Monte Carlo permutation analysis.
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default UnifiedBacktestPane;
