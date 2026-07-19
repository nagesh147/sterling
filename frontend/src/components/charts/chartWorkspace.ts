export type ExtraIndicatorKind = 'ema' | 'sma' | 'rsi' | 'atr' | 'stochastic' | 'formula';
export type ComparisonMode = 'price' | 'percent';

export interface IndicatorStyle {
  color: string;
  secondaryColor?: string;
  lineWidth: 1 | 2 | 3 | 4;
  visible: boolean;
}

export interface ExtraIndicator {
  id: string;
  kind: ExtraIndicatorKind;
  name: string;
  period: number;
  formula?: string;
  style: IndicatorStyle;
}

export interface ChartAppearance {
  candleUp: string;
  candleDown: string;
  gridVisible: boolean;
  magnetCrosshair: boolean;
}

export interface ComparisonOverlay {
  id: string;
  symbol: string;
  color: string;
  mode: ComparisonMode;
  visible: boolean;
}

export interface ChartWorkspaceState {
  styles: Record<string, IndicatorStyle>;
  extraIndicators: ExtraIndicator[];
  compareSymbol: string | null;
  comparisons: ComparisonOverlay[];
  appearance: ChartAppearance;
}

export interface ChartTemplateSnapshot {
  tf: string;
  chartType: 'candles' | 'line' | 'area' | 'bars';
  layoutMode: '1' | '2' | '4';
  isHA: boolean;
  isLogScale: boolean;
  showVP: boolean;
  activeIndicators: string[];
  params: Record<string, unknown>;
  workspace: ChartWorkspaceState;
}

export interface ChartTemplate {
  id: string;
  name: string;
  createdAt: number;
  snapshot: ChartTemplateSnapshot;
}

export const WORKSPACE_KEY = 'sterling:kite-chart-workspace:v1';
export const TEMPLATE_KEY = 'sterling:kite-chart-templates:v1';
export const MAX_EXTRA_INDICATORS = 24;
export const MAX_COMPARISONS = 4;
export const MAX_TEMPLATES = 40;
export const MAX_INDICATOR_PERIOD = 500;
export const REPLAY_SPEEDS = [0.25, 0.5, 1, 2, 4] as const;
export const DEFAULT_COMPARISON_COLORS = ['#ff9800', '#2962ff', '#ab47bc', '#26a69a'] as const;

export const DEFAULT_APPEARANCE: ChartAppearance = {
  candleUp: '#2db784',
  candleDown: '#e05260',
  gridVisible: false,
  magnetCrosshair: true,
};

export const DEFAULT_WORKSPACE: ChartWorkspaceState = {
  styles: {},
  extraIndicators: [],
  compareSymbol: null,
  comparisons: [],
  appearance: DEFAULT_APPEARANCE,
};

const KIND_DEFAULTS: Record<ExtraIndicatorKind, Omit<ExtraIndicator, 'id'>> = {
  ema: { kind: 'ema', name: 'EMA', period: 20, style: { color: '#2962ff', lineWidth: 2, visible: true } },
  sma: { kind: 'sma', name: 'SMA', period: 50, style: { color: '#ff9800', lineWidth: 2, visible: true } },
  rsi: { kind: 'rsi', name: 'RSI', period: 14, style: { color: '#7e57c2', lineWidth: 2, visible: true } },
  atr: { kind: 'atr', name: 'ATR', period: 14, style: { color: '#26a69a', lineWidth: 2, visible: true } },
  stochastic: { kind: 'stochastic', name: 'Stochastic %K', period: 14, style: { color: '#ab47bc', lineWidth: 2, visible: true } },
  formula: { kind: 'formula', name: 'Custom formula', period: 1, formula: 'hlc3', style: { color: '#ef5350', lineWidth: 2, visible: true } },
};

export function createExtraIndicator(kind: ExtraIndicatorKind, now = Date.now()): ExtraIndicator {
  return { ...KIND_DEFAULTS[kind], id: `${kind}-${now}`, style: { ...KIND_DEFAULTS[kind].style } };
}

export function createComparisonOverlay(symbol: string, now = Date.now(), index = 0): ComparisonOverlay {
  const normalized = normalizeSymbol(symbol);
  if (!normalized) throw new Error('Comparison symbol is required');
  return {
    id: `compare-${now}-${index}`,
    symbol: normalized,
    color: DEFAULT_COMPARISON_COLORS[index % DEFAULT_COMPARISON_COLORS.length],
    mode: 'percent',
    visible: true,
  };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function cloneWorkspace(): ChartWorkspaceState {
  return {
    styles: {},
    extraIndicators: [],
    compareSymbol: null,
    comparisons: [],
    appearance: { ...DEFAULT_APPEARANCE },
  };
}

function isColor(value: unknown): value is string {
  return typeof value === 'string' && /^#[0-9a-f]{3}([0-9a-f]{3})?$/i.test(value.trim());
}

function normalizePeriod(value: unknown, fallback: number): number {
  const period = Math.floor(Number(value));
  if (!Number.isFinite(period)) return fallback;
  return Math.min(MAX_INDICATOR_PERIOD, Math.max(1, period));
}

function normalizeSymbol(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const next = value.trim().toUpperCase().replace(/\s+/g, ' ');
  return next ? next.slice(0, 80) : null;
}

function normalizeComparisonMode(value: unknown): ComparisonMode {
  return value === 'price' || value === 'percent' ? value : 'percent';
}

function normalizeComparisons(value: unknown, legacySymbol: unknown): ComparisonOverlay[] {
  const seen = new Set<string>();
  const rawComparisons = Array.isArray(value) ? value : [];
  const fromComparisons = rawComparisons.flatMap((item, index): ComparisonOverlay[] => {
    if (!isObject(item)) return [];
    const symbol = normalizeSymbol(item.symbol);
    if (!symbol || seen.has(symbol)) return [];
    seen.add(symbol);
    const baseId = typeof item.id === 'string' && item.id.trim() ? item.id.trim().slice(0, 80) : `compare-${index}`;
    return [{
      id: baseId,
      symbol,
      color: isColor(item.color) ? item.color : DEFAULT_COMPARISON_COLORS[index % DEFAULT_COMPARISON_COLORS.length],
      mode: normalizeComparisonMode(item.mode),
      visible: typeof item.visible === 'boolean' ? item.visible : true,
    }];
  });
  const legacy = normalizeSymbol(legacySymbol);
  if (legacy && !seen.has(legacy)) {
    fromComparisons.unshift({
      id: 'compare-legacy',
      symbol: legacy,
      color: DEFAULT_COMPARISON_COLORS[0],
      mode: 'percent',
      visible: true,
    });
  }
  return fromComparisons.slice(0, MAX_COMPARISONS);
}

function normalizeStyle(value: unknown, fallback: IndicatorStyle): IndicatorStyle {
  const raw = isObject(value) ? value : {};
  const width = Number(raw.lineWidth);
  return {
    color: isColor(raw.color) ? raw.color : fallback.color,
    secondaryColor: isColor(raw.secondaryColor) ? raw.secondaryColor : fallback.secondaryColor,
    lineWidth: ([1, 2, 3, 4].includes(width) ? width : fallback.lineWidth) as IndicatorStyle['lineWidth'],
    visible: typeof raw.visible === 'boolean' ? raw.visible : fallback.visible,
  };
}

export function normalizeWorkspace(value: unknown): ChartWorkspaceState {
  if (!isObject(value)) return cloneWorkspace();
  const rawStyles = isObject(value.styles) ? value.styles : {};
  const styles: Record<string, IndicatorStyle> = {};
  for (const [key, style] of Object.entries(rawStyles)) {
    styles[key] = normalizeStyle(style, { color: '#2962ff', lineWidth: 2, visible: true });
  }

  const seenIds = new Set<string>();
  const extraIndicators = Array.isArray(value.extraIndicators)
    ? value.extraIndicators.flatMap((item): ExtraIndicator[] => {
        if (!isObject(item) || typeof item.id !== 'string' || typeof item.kind !== 'string') return [];
        if (!(item.kind in KIND_DEFAULTS)) return [];
        const fallback = KIND_DEFAULTS[item.kind as ExtraIndicatorKind];
        const baseId = item.id.trim() || `${item.kind}-${seenIds.size}`;
        let id = baseId;
        let suffix = 2;
        while (seenIds.has(id)) {
          id = `${baseId}-${suffix}`;
          suffix += 1;
        }
        seenIds.add(id);
        return [{
          id,
          kind: item.kind as ExtraIndicatorKind,
          name: typeof item.name === 'string' && item.name.trim() ? item.name.trim().slice(0, 48) : fallback.name,
          period: normalizePeriod(item.period, fallback.period),
          formula: typeof item.formula === 'string' ? item.formula : fallback.formula,
          style: normalizeStyle(item.style, fallback.style),
        }];
      }).slice(0, MAX_EXTRA_INDICATORS)
    : [];

  const appearanceRaw = isObject(value.appearance) ? value.appearance : {};
  const comparisons = normalizeComparisons(value.comparisons, value.compareSymbol);
  return {
    styles,
    extraIndicators,
    compareSymbol: comparisons[0]?.symbol ?? null,
    comparisons,
    appearance: {
      candleUp: isColor(appearanceRaw.candleUp) ? appearanceRaw.candleUp : DEFAULT_APPEARANCE.candleUp,
      candleDown: isColor(appearanceRaw.candleDown) ? appearanceRaw.candleDown : DEFAULT_APPEARANCE.candleDown,
      gridVisible: typeof appearanceRaw.gridVisible === 'boolean' ? appearanceRaw.gridVisible : DEFAULT_APPEARANCE.gridVisible,
      magnetCrosshair: typeof appearanceRaw.magnetCrosshair === 'boolean' ? appearanceRaw.magnetCrosshair : DEFAULT_APPEARANCE.magnetCrosshair,
    },
  };
}

export function loadWorkspace(storage: Pick<Storage, 'getItem'> = localStorage): ChartWorkspaceState {
  try {
    const raw = storage.getItem(WORKSPACE_KEY);
    return raw ? normalizeWorkspace(JSON.parse(raw)) : cloneWorkspace();
  } catch {
    return cloneWorkspace();
  }
}

export function saveWorkspace(state: ChartWorkspaceState, storage: Pick<Storage, 'setItem'> = localStorage): void {
  storage.setItem(WORKSPACE_KEY, JSON.stringify(normalizeWorkspace(state)));
}

const CHART_TYPES = ['candles', 'line', 'area', 'bars'] as const;
const LAYOUT_MODES = ['1', '2', '4'] as const;

function normalizeSnapshot(value: unknown): ChartTemplateSnapshot {
  const raw = isObject(value) ? value : {};
  const chartType = CHART_TYPES.includes(raw.chartType as any) ? raw.chartType as ChartTemplateSnapshot['chartType'] : 'candles';
  const layoutMode = LAYOUT_MODES.includes(raw.layoutMode as any) ? raw.layoutMode as ChartTemplateSnapshot['layoutMode'] : '1';
  const activeIndicators = Array.isArray(raw.activeIndicators)
    ? Array.from(new Set(raw.activeIndicators.filter((item): item is string => typeof item === 'string' && !!item.trim()).map((item) => item.trim()))).slice(0, 32)
    : [];
  return {
    tf: typeof raw.tf === 'string' && raw.tf ? raw.tf : '15m',
    chartType,
    layoutMode,
    isHA: !!raw.isHA,
    isLogScale: !!raw.isLogScale,
    showVP: !!raw.showVP,
    activeIndicators,
    params: isObject(raw.params) ? { ...raw.params } : {},
    workspace: normalizeWorkspace(raw.workspace),
  };
}

export function normalizeTemplates(value: unknown): ChartTemplate[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  return value.flatMap((item, index): ChartTemplate[] => {
    if (!isObject(item)) return [];
    const name = typeof item.name === 'string' && item.name.trim() ? item.name.trim().slice(0, 80) : '';
    if (!name) return [];
    const baseId = typeof item.id === 'string' && item.id.trim() ? item.id.trim().slice(0, 80) : `template-${index}`;
    let id = baseId;
    let suffix = 2;
    while (seen.has(id)) {
      id = `${baseId}-${suffix}`;
      suffix += 1;
    }
    seen.add(id);
    const createdAt = Number(item.createdAt);
    return [{
      id,
      name,
      createdAt: Number.isFinite(createdAt) && createdAt > 0 ? createdAt : Date.now(),
      snapshot: normalizeSnapshot(item.snapshot),
    }];
  }).slice(0, MAX_TEMPLATES);
}

export function loadTemplates(storage: Pick<Storage, 'getItem'> = localStorage): ChartTemplate[] {
  try {
    const raw = storage.getItem(TEMPLATE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return normalizeTemplates(parsed);
  } catch {
    return [];
  }
}

export function saveTemplates(templates: ChartTemplate[], storage: Pick<Storage, 'setItem'> = localStorage): void {
  storage.setItem(TEMPLATE_KEY, JSON.stringify(normalizeTemplates(templates)));
}

export function createChartTemplate(name: string, snapshot: ChartTemplateSnapshot, now = Date.now()): ChartTemplate {
  const normalized = normalizeTemplates([{ id: `template-${now}`, name, createdAt: now, snapshot }])[0];
  if (!normalized) throw new Error('Template name is required');
  return normalized;
}

export function upsertTemplate(templates: ChartTemplate[], template: ChartTemplate): ChartTemplate[] {
  const normalized = normalizeTemplates([template])[0];
  if (!normalized) return normalizeTemplates(templates);
  const key = normalized.name.toLowerCase();
  const retained = normalizeTemplates(templates).filter((item) => item.id !== normalized.id && item.name.toLowerCase() !== key);
  return [normalized, ...retained].slice(0, MAX_TEMPLATES);
}

export function exportTemplatesToJson(templates: ChartTemplate[], exportedAt = Date.now()): string {
  return JSON.stringify({ version: 1, exportedAt, templates: normalizeTemplates(templates) }, null, 2);
}

export function mergeImportedTemplates(rawJson: string, existing: ChartTemplate[] = []): ChartTemplate[] {
  const parsed = JSON.parse(rawJson);
  const incoming = normalizeTemplates(Array.isArray(parsed) ? parsed : isObject(parsed) ? parsed.templates : []);
  return incoming.reduce((all, template) => upsertTemplate(all, template), normalizeTemplates(existing));
}

type FormulaContext = Record<string, number>;

const FORMULA_FUNCTIONS: Record<string, (...args: number[]) => number> = {
  abs: Math.abs,
  ceil: Math.ceil,
  floor: Math.floor,
  log: Math.log,
  max: Math.max,
  min: Math.min,
  pow: Math.pow,
  round: Math.round,
  sqrt: Math.sqrt,
};

export function compileFormula(expression: string): (context: FormulaContext) => number {
  const parser = new FormulaParser(expression);
  const evaluate = parser.parse();
  return (context) => {
    const value = evaluate(context);
    return Number.isFinite(value) ? value : Number.NaN;
  };
}

type FormulaEvaluator = (context: FormulaContext) => number;

class FormulaParser {
  private pos = 0;

  constructor(private readonly input: string) {}

  parse(): FormulaEvaluator {
    const expression = this.parseConditional();
    this.skipWhitespace();
    if (this.pos !== this.input.length) throw new Error(`Unexpected token: ${this.input[this.pos]}`);
    return expression;
  }

  private parseConditional(): FormulaEvaluator {
    const test = this.parseComparison();
    this.skipWhitespace();
    if (!this.consume('?')) return test;
    const consequent = this.parseConditional();
    this.expect(':');
    const alternate = this.parseConditional();
    return (context) => test(context) ? consequent(context) : alternate(context);
  }

  private parseComparison(): FormulaEvaluator {
    let left = this.parseAdditive();
    while (true) {
      this.skipWhitespace();
      const op = this.consumeOperator(['===', '!==', '>=', '<=', '==', '!=', '>', '<']);
      if (!op) return left;
      const right = this.parseAdditive();
      const previous = left;
      left = (context) => {
        const a = previous(context);
        const b = right(context);
        switch (op) {
          case '>': return a > b ? 1 : 0;
          case '>=': return a >= b ? 1 : 0;
          case '<': return a < b ? 1 : 0;
          case '<=': return a <= b ? 1 : 0;
          case '==':
          case '===': return a === b ? 1 : 0;
          case '!=':
          case '!==': return a !== b ? 1 : 0;
          default: return Number.NaN;
        }
      };
    }
  }

  private parseAdditive(): FormulaEvaluator {
    let left = this.parseMultiplicative();
    while (true) {
      this.skipWhitespace();
      const op = this.consumeOperator(['+', '-']);
      if (!op) return left;
      const right = this.parseMultiplicative();
      const previous = left;
      left = op === '+'
        ? (context) => previous(context) + right(context)
        : (context) => previous(context) - right(context);
    }
  }

  private parseMultiplicative(): FormulaEvaluator {
    let left = this.parsePower();
    while (true) {
      this.skipWhitespace();
      const op = this.consumeOperator(['*', '/', '%']);
      if (!op) return left;
      const right = this.parsePower();
      const previous = left;
      left = (context) => {
        const a = previous(context);
        const b = right(context);
        if (op === '*') return a * b;
        if (op === '/') return b === 0 ? Number.NaN : a / b;
        return b === 0 ? Number.NaN : a % b;
      };
    }
  }

  private parsePower(): FormulaEvaluator {
    const left = this.parseUnary();
    this.skipWhitespace();
    if (!this.consume('^')) return left;
    const right = this.parsePower();
    return (context) => Math.pow(left(context), right(context));
  }

  private parseUnary(): FormulaEvaluator {
    this.skipWhitespace();
    if (this.consume('+')) return this.parseUnary();
    if (this.consume('-')) {
      const value = this.parseUnary();
      return (context) => -value(context);
    }
    if (this.consume('!')) {
      const value = this.parseUnary();
      return (context) => value(context) ? 0 : 1;
    }
    return this.parsePrimary();
  }

  private parsePrimary(): FormulaEvaluator {
    this.skipWhitespace();
    if (this.consume('(')) {
      const expression = this.parseConditional();
      this.expect(')');
      return expression;
    }
    const numeric = this.parseNumber();
    if (numeric) return numeric;
    const identifier = this.parseIdentifier();
    if (identifier) {
      this.skipWhitespace();
      if (this.consume('(')) {
        const fn = FORMULA_FUNCTIONS[identifier];
        if (!fn) throw new Error('Only approved math functions are allowed');
        const args: FormulaEvaluator[] = [];
        this.skipWhitespace();
        if (!this.consume(')')) {
          do {
            args.push(this.parseConditional());
            this.skipWhitespace();
          } while (this.consume(','));
          this.expect(')');
        }
        return (context) => fn(...args.map((arg) => arg(context)));
      }
      return (context) => {
        if (!(identifier in context)) throw new Error(`Unknown variable: ${identifier}`);
        return context[identifier];
      };
    }
    throw new Error(`Unexpected token: ${this.input[this.pos] ?? 'end of expression'}`);
  }

  private parseNumber(): FormulaEvaluator | null {
    this.skipWhitespace();
    const rest = this.input.slice(this.pos);
    const match = rest.match(/^(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?/i);
    if (!match) return null;
    this.pos += match[0].length;
    const value = Number(match[0]);
    if (!Number.isFinite(value)) throw new Error('Invalid numeric literal');
    return () => value;
  }

  private parseIdentifier(): string | null {
    this.skipWhitespace();
    const rest = this.input.slice(this.pos);
    const match = rest.match(/^[A-Za-z_][A-Za-z0-9_]*/);
    if (!match) return null;
    this.pos += match[0].length;
    return match[0];
  }

  private skipWhitespace(): void {
    while (/\s/.test(this.input[this.pos] || '')) this.pos += 1;
  }

  private consume(token: string): boolean {
    this.skipWhitespace();
    if (!this.input.startsWith(token, this.pos)) return false;
    this.pos += token.length;
    return true;
  }

  private expect(token: string): void {
    if (!this.consume(token)) throw new Error(`Expected "${token}"`);
  }

  private consumeOperator(operators: string[]): string | null {
    this.skipWhitespace();
    const op = operators.find((operator) => this.input.startsWith(operator, this.pos));
    if (!op) return null;
    this.pos += op.length;
    return op;
  }
}

export function formulaSeries(expression: string, candles: Array<{ open: number; high: number; low: number; close: number; volume?: number }>): Array<number | null> {
  const evaluate = compileFormula(expression);
  return candles.map((candle, index) => {
    try {
      const previousClose = index > 0 ? candles[index - 1].close : candle.close;
      const value = evaluate({
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        volume: candle.volume ?? 0,
        hl2: (candle.high + candle.low) / 2,
        hlc3: (candle.high + candle.low + candle.close) / 3,
        ohlc4: (candle.open + candle.high + candle.low + candle.close) / 4,
        change: candle.close - previousClose,
        index,
      });
      return Number.isFinite(value) ? value : null;
    } catch {
      return null;
    }
  });
}

export function comparisonSeriesData(
  candles: Array<{ time: number; close: number }>,
  mode: ComparisonMode,
): Array<{ time: number; value: number }> {
  const firstClose = candles.find((candle) => Number.isFinite(candle.close) && candle.close > 0)?.close ?? null;
  return candles.flatMap((candle) => {
    if (!Number.isFinite(candle.time) || !Number.isFinite(candle.close)) return [];
    if (mode === 'percent') {
      if (!firstClose) return [];
      return [{ time: candle.time, value: ((candle.close - firstClose) / firstClose) * 100 }];
    }
    return [{ time: candle.time, value: candle.close }];
  });
}

export function stochastic(highs: number[], lows: number[], closes: number[], period: number): Array<number | null> {
  return closes.map((close, index) => {
    if (index < period - 1) return null;
    const windowHigh = Math.max(...highs.slice(index - period + 1, index + 1));
    const windowLow = Math.min(...lows.slice(index - period + 1, index + 1));
    return windowHigh === windowLow ? 50 : ((close - windowLow) / (windowHigh - windowLow)) * 100;
  });
}

export function nearestCandleIndex(candles: Array<{ time: number }>, timestampSeconds: number): number {
  if (!candles.length) return -1;
  let low = 0;
  let high = candles.length - 1;
  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (candles[mid].time < timestampSeconds) low = mid + 1;
    else high = mid;
  }
  if (low === 0) return 0;
  return Math.abs(candles[low].time - timestampSeconds) < Math.abs(candles[low - 1].time - timestampSeconds) ? low : low - 1;
}

export function replayDelayMs(speed: number): number {
  const sanitized = REPLAY_SPEEDS.includes(speed as any) ? speed : 1;
  return Math.round(700 / sanitized);
}

export function stepReplayIndex(current: number | null, maxIndex: number, delta: number): number | null {
  if (maxIndex < 0) return null;
  const base = current == null ? maxIndex : current;
  return Math.max(0, Math.min(maxIndex, base + delta));
}
