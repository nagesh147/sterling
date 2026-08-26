import type { GapKind, Regime, TradeAction, TradeSide } from '../../../lib/astro/types';
import type { GradeKind } from '../../../lib/astro/tape';

export function regimeTone(regime: Regime): { fg: string; bg: string; bar: string } {
  if (regime.includes('Positive') && regime.includes('Strong')) {
    return { fg: 'text-up', bg: 'bg-up/12', bar: 'bg-up' };
  }
  if (regime.includes('Positive')) {
    return { fg: 'text-up', bg: 'bg-up/8', bar: 'bg-up/80' };
  }
  if (regime.includes('Negative') && regime.includes('Strong')) {
    return { fg: 'text-down', bg: 'bg-down/12', bar: 'bg-down' };
  }
  if (regime.includes('Negative')) {
    return { fg: 'text-down', bg: 'bg-down/8', bar: 'bg-down/80' };
  }
  return { fg: 'text-warn', bg: 'bg-warn/10', bar: 'bg-warn' };
}

export function gapTone(kind: GapKind): { fg: string; label: string } {
  if (kind === 'up') return { fg: 'text-up', label: 'GAP UP' };
  if (kind === 'down') return { fg: 'text-down', label: 'GAP DOWN' };
  return { fg: 'text-warn', label: 'FLAT' };
}

export function actionTone(action: TradeAction, side: TradeSide): string {
  if (action === 'AVOID' || action === 'WAIT') return 'text-muted';
  if (side === 'CE') return 'text-ce';
  if (side === 'PE') return 'text-pe';
  return 'text-warn';
}

export function choTone(kind: 'good' | 'move' | 'bad'): string {
  if (kind === 'good') return 'text-up';
  if (kind === 'bad') return 'text-down';
  return 'text-warn';
}

export function gradeTone(kind: GradeKind): string {
  if (kind === 'HIT') return 'text-up';
  if (kind === 'MISS') return 'text-down';
  if (kind === 'LIVE') return 'text-ink';
  if (kind === 'SIT') return 'text-muted';
  return 'text-faint';
}

export const REGIME_SHORT: Record<Regime, string> = {
  'Strong Positive': 'Strong +',
  Positive: 'Positive',
  'Volatile Positive': 'Vol +',
  'Sideways to Positive': 'Side +',
  'Sideways/Volatile': 'Side / Vol',
  'Sideways to Negative': 'Side −',
  'Volatile Negative': 'Vol −',
  Negative: 'Negative',
  'Strong Negative': 'Strong −',
};
