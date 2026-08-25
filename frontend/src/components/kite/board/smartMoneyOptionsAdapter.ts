import type { BoardInstrument, BoardOrigin, BoardSection, BoardSignal, BoardStatus } from './boardTypes';
import type { SmartMoneySnapshot, SmartMoneySignal } from '../../../hooks/useSmartMoneyOptions';
import type { Stat } from './StatCard';

const price = (v: number | null | undefined): number | null =>
  v == null || !Number.isFinite(v) || v <= 0 ? null : v;

function originOf(sig: SmartMoneySignal): BoardOrigin {
  if (sig.rvol >= 2.0) {
    return {
      label: 'INSTITUTIONAL SURGE',
      tone: 'green',
      hint: `Smart Money relative volume is ${sig.rvol.toFixed(1)}x with strong delta pressure.`,
    };
  }
  if (sig.rvol >= 1.5) {
    return {
      label: 'VOLUME BREAKOUT',
      tone: 'blue',
      hint: `Volume expansion ${sig.rvol.toFixed(1)}x above 20-period average.`,
    };
  }
  return {
    label: 'CONSOLIDATION',
    tone: 'dim',
    hint: `Base structure: ${sig.structure_phase}`,
  };
}

function instrumentOf(sig: SmartMoneySignal): BoardInstrument {
  const symbol = sig.tradingsymbol || `${sig.symbol} ${sig.strike ?? ''} ${sig.option_type ?? ''}`.trim();
  return {
    symbol,
    exchange: 'NFO',
    kind: 'option',
    optionType: sig.option_type,
    strike: sig.strike ?? null,
    expiry: sig.expiry ?? null,
    lotSize: null,
    quoteKey: sig.tradingsymbol ? `NFO:${sig.tradingsymbol}` : null,
  };
}

import { k } from '../../../styles/kiteUI';

function sectionsOf(sig: SmartMoneySignal): BoardSection[] {
  const sections: BoardSection[] = [];

  // Structure Section
  const structStats: Stat[] = [
    { label: 'PHASE', value: sig.structure_phase, color: k.blue, hint: 'Market base consolidation/breakout phase' },
    { label: 'SPOT PRICE', value: `₹${sig.spot_price.toLocaleString('en-IN')}`, hint: 'Underlying equity/index price' },
    { label: 'SPOT STOP LOSS', value: sig.stop_loss_spot ? `₹${sig.stop_loss_spot.toLocaleString('en-IN')}` : '—', color: k.dim, hint: 'Structural swing low support level' },
    { label: 'SWING HORIZON', value: `${sig.holding_period_days} Days`, hint: 'Target swing holding duration' },
  ];
  sections.push({
    title: 'Market Structure & Liquidity',
    stats: structStats,
  });

  // Smart Money Footprint Section
  const smStats: Stat[] = [
    { label: 'RVOL (SURGE)', value: `${sig.rvol.toFixed(2)}x`, color: sig.rvol >= 1.8 ? k.green : undefined, hint: 'Relative volume vs 20-period average' },
    { label: 'FOOTPRINT SCORE', value: `${sig.footprint_score.toFixed(1)} / 100`, color: sig.footprint_score >= 70 ? k.green : undefined, hint: 'Smart money aggression & delta rating' },
    { label: 'CONVICTION', value: `${Math.round(sig.confidence * 100)}%`, color: k.blue, hint: 'Composite setup confidence' },
  ];
  sections.push({
    title: 'Smart Money Footprint',
    stats: smStats,
  });

  // Multi-X Targets Section
  if (sig.targets) {
    const targetStats: Stat[] = [
      { label: 'ENTRY PREMIUM', value: sig.entry_premium ? `₹${sig.entry_premium.toFixed(2)}` : '—', hint: 'Estimated option entry price' },
      { label: 'TARGET 1 (2X)', value: `₹${sig.targets.target_1_2x.toFixed(2)}`, color: k.green, hint: '+100% gain (Trail to Breakeven)' },
      { label: 'TARGET 2 (3X)', value: `₹${sig.targets.target_2_3x.toFixed(2)}`, color: k.green, hint: '+200% gain' },
      { label: 'TARGET 3 (5X MULTI-X)', value: `₹${sig.targets.target_3_5x.toFixed(2)}`, color: k.green, hint: '+400% gain (Multi-X Runner)' },
      { label: 'STOP LOSS', value: sig.stop_loss_premium ? `₹${sig.stop_loss_premium.toFixed(2)}` : '—', color: k.dim, hint: 'Premium stop loss' },
    ];
    sections.push({
      title: 'Multi-X Target Architecture',
      stats: targetStats,
    });
  }

  return sections;
}

export function smartMoneySignalToBoard(sig: SmartMoneySignal): BoardSignal {
  const statusMap: Record<string, BoardStatus> = {
    armed: 'armed',
    running: 'running',
    ended: 'ended',
    watching: 'watching',
  };

  const currentStatus: BoardStatus = statusMap[sig.status] || (sig.action !== 'NO_TRADE' ? 'armed' : 'watching');
  const entry = price(sig.entry_premium);
  const stop = price(sig.stop_loss_premium);
  const target = sig.targets ? price(sig.targets.target_3_5x) : null;
  const trail = sig.targets ? price(sig.targets.target_1_2x) : null;

  return {
    id: `smx-${sig.symbol}-${sig.timestamp_ms || Date.now()}`,
    engine: 'smart_money_options',
    underlying: sig.symbol,
    status: currentStatus,
    direction: sig.action === 'BUY_PE' ? 'short' : 'long',
    instrument: instrumentOf(sig),
    origin: originOf(sig),
    atMs: sig.timestamp_ms || Date.now(),
    levels: {
      ltp: entry,
      entry,
      stop,
      trail,
      target,
      exit: null,
    },
    sizing: {
      lots: 1,
      quantity: 1,
      atRiskInr: entry != null && stop != null ? (entry - stop) : null,
      deployedInr: entry != null ? entry : null,
    },
    score: Math.round(sig.footprint_score),
    reason: sig.reason,
    quoteAgeS: null,
    sections: sectionsOf(sig),
  };
}

export function smartMoneyOptionsToBoard(snapshot: SmartMoneySnapshot | undefined | null): BoardSignal[] {
  if (!snapshot || !snapshot.signals) return [];
  return snapshot.signals.map(smartMoneySignalToBoard);
}
