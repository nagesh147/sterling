import jsep from 'jsep';

export type ExtraIndicatorKind = 'ema' | 'sma' | 'rsi' | 'atr' | 'stochastic' | 'formula';

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

export interface ChartWorkspaceState {
  styles: Record<string, IndicatorStyle>;
  extraIndicators: ExtraIndicator[];
  compareSymbol: string | null;
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
export const MAX_TEMPLATES = 40;
export const MAX_INDICATOR_PERIOD = 500;
export const REPLAY_SPEEDS = [0.25, 0.5, 1, 2, 4] as const;

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

function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function cloneWorkspace(): ChartWorkspaceState {
  return {
    styles: {},
    extraIndicators: [],
    compareSymbol: null,
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
  return {
    styles,
    extraIndicators,
    compareSymbol: normalizeSymbol(value.compareSymbol),
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

function evaluateNode(node: any, context: FormulaContext): number {
  switch (node.type) {
    case 'Literal':
      if (typeof node.value !== 'number') throw new Error('Only numeric literals are allowed');
      return node.value;
    case 'Identifier':
      if (!(node.name in context)) throw new Error(`Unknown variable: ${node.name}`);
      return context[node.name];
    case 'UnaryExpression': {
      const value = evaluateNode(node.argument, context);
      if (node.operator === '+') return value;
      if (node.operator === '-') return -value;
      if (node.operator === '!') return value ? 0 : 1;
      throw new Error(`Unsupported operator: ${node.operator}`);
    }
    case 'BinaryExpression': {
      const left = evaluateNode(node.left, context);
      const right = evaluateNode(node.right, context);
      switch (node.operator) {
        case '+': return left + right;
        case '-': return left - right;
        case '*': return left * right;
        case '/': return right === 0 ? Number.NaN : left / right;
        case '%': return right === 0 ? Number.NaN : left % right;
        case '^': return Math.pow(left, right);
        case '>': return left > right ? 1 : 0;
        case '>=': return left >= right ? 1 : 0;
        case '<': return left < right ? 1 : 0;
        case '<=': return left <= right ? 1 : 0;
        case '==': case '===': return left === right ? 1 : 0;
        case '!=': case '!==': return left !== right ? 1 : 0;
        default: throw new Error(`Unsupported operator: ${node.operator}`);
      }
    }
    case 'CallExpression': {
      if (node.callee?.type !== 'Identifier' || !(node.callee.name in FORMULA_FUNCTIONS)) {
        throw new Error('Only approved math functions are allowed');
      }
      return FORMULA_FUNCTIONS[node.callee.name](...node.arguments.map((arg: any) => evaluateNode(arg, context)));
    }
    case 'ConditionalExpression':
      return evaluateNode(node.test, context) ? evaluateNode(node.consequent, context) : evaluateNode(node.alternate, context);
    default:
      throw new Error(`Unsupported expression: ${node.type}`);
  }
}

export function compileFormula(expression: string): (context: FormulaContext) => number {
  const ast = jsep(expression);
  return (context) => {
    const value = evaluateNode(ast, context);
    return Number.isFinite(value) ? value : Number.NaN;
  };
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
