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

const WORKSPACE_KEY = 'sterling:kite-chart-workspace:v1';
const TEMPLATE_KEY = 'sterling:kite-chart-templates:v1';

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

function normalizeStyle(value: unknown, fallback: IndicatorStyle): IndicatorStyle {
  const raw = isObject(value) ? value : {};
  const width = Number(raw.lineWidth);
  return {
    color: typeof raw.color === 'string' ? raw.color : fallback.color,
    secondaryColor: typeof raw.secondaryColor === 'string' ? raw.secondaryColor : fallback.secondaryColor,
    lineWidth: ([1, 2, 3, 4].includes(width) ? width : fallback.lineWidth) as IndicatorStyle['lineWidth'],
    visible: typeof raw.visible === 'boolean' ? raw.visible : fallback.visible,
  };
}

export function normalizeWorkspace(value: unknown): ChartWorkspaceState {
  if (!isObject(value)) return structuredClone(DEFAULT_WORKSPACE);
  const rawStyles = isObject(value.styles) ? value.styles : {};
  const styles: Record<string, IndicatorStyle> = {};
  for (const [key, style] of Object.entries(rawStyles)) {
    styles[key] = normalizeStyle(style, { color: '#2962ff', lineWidth: 2, visible: true });
  }

  const extraIndicators = Array.isArray(value.extraIndicators)
    ? value.extraIndicators.flatMap((item): ExtraIndicator[] => {
        if (!isObject(item) || typeof item.id !== 'string' || typeof item.kind !== 'string') return [];
        if (!(item.kind in KIND_DEFAULTS)) return [];
        const fallback = KIND_DEFAULTS[item.kind as ExtraIndicatorKind];
        return [{
          id: item.id,
          kind: item.kind as ExtraIndicatorKind,
          name: typeof item.name === 'string' ? item.name : fallback.name,
          period: Math.max(1, Number(item.period) || fallback.period),
          formula: typeof item.formula === 'string' ? item.formula : fallback.formula,
          style: normalizeStyle(item.style, fallback.style),
        }];
      })
    : [];

  const appearanceRaw = isObject(value.appearance) ? value.appearance : {};
  return {
    styles,
    extraIndicators,
    compareSymbol: typeof value.compareSymbol === 'string' && value.compareSymbol ? value.compareSymbol : null,
    appearance: {
      candleUp: typeof appearanceRaw.candleUp === 'string' ? appearanceRaw.candleUp : DEFAULT_APPEARANCE.candleUp,
      candleDown: typeof appearanceRaw.candleDown === 'string' ? appearanceRaw.candleDown : DEFAULT_APPEARANCE.candleDown,
      gridVisible: typeof appearanceRaw.gridVisible === 'boolean' ? appearanceRaw.gridVisible : DEFAULT_APPEARANCE.gridVisible,
      magnetCrosshair: typeof appearanceRaw.magnetCrosshair === 'boolean' ? appearanceRaw.magnetCrosshair : DEFAULT_APPEARANCE.magnetCrosshair,
    },
  };
}

export function loadWorkspace(storage: Pick<Storage, 'getItem'> = localStorage): ChartWorkspaceState {
  try {
    const raw = storage.getItem(WORKSPACE_KEY);
    return raw ? normalizeWorkspace(JSON.parse(raw)) : structuredClone(DEFAULT_WORKSPACE);
  } catch {
    return structuredClone(DEFAULT_WORKSPACE);
  }
}

export function saveWorkspace(state: ChartWorkspaceState, storage: Pick<Storage, 'setItem'> = localStorage): void {
  storage.setItem(WORKSPACE_KEY, JSON.stringify(normalizeWorkspace(state)));
}

export function loadTemplates(storage: Pick<Storage, 'getItem'> = localStorage): ChartTemplate[] {
  try {
    const raw = storage.getItem(TEMPLATE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) => isObject(item) && typeof item.id === 'string' && typeof item.name === 'string' && isObject(item.snapshot)) as unknown as ChartTemplate[];
  } catch {
    return [];
  }
}

export function saveTemplates(templates: ChartTemplate[], storage: Pick<Storage, 'setItem'> = localStorage): void {
  storage.setItem(TEMPLATE_KEY, JSON.stringify(templates));
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
