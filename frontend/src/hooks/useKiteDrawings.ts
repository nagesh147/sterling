import { useState, useCallback, useRef, useEffect } from 'react';

export interface Drawing {
  id: number;
  type: string;
  price?: number;
  points?: { time: number; price: number }[];
  time?: number;
  text?: string;
  color?: string;
  variant?: string; // e.g. 'retr' | 'ext' | 'fan' for fibs
}

interface UseKiteDrawingsOptions {
  initialDrawings?: Drawing[];
  onChange?: (drawings: Drawing[]) => void;
}

export function useKiteDrawings({ initialDrawings = [], onChange }: UseKiteDrawingsOptions = {}) {
  const [drawings, _setDrawings] = useState<Drawing[]>(initialDrawings);
  const [drawMode, setDrawMode] = useState<'crosshair' | 'hline' | 'trend' | 'ray' | 'fib' | 'fibext' | 'fibfan' | 'rect' | 'text' | 'pitchfork'>('crosshair');
  const [drawingPoints, setDrawingPoints] = useState<any[]>([]);
  const [selectedDrawingId, setSelectedDrawingId] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragInfo, setDragInfo] = useState<any>(null);

  const setDrawings = useCallback((newDrawings: Drawing[] | ((prev: Drawing[]) => Drawing[])) => {
    _setDrawings(newDrawings);
    if (onChange) {
      const updated = typeof newDrawings === 'function' ? newDrawings(drawings) : newDrawings;
      onChange(updated);
    }
  }, [onChange, drawings]);

  const saveTimeoutRef = useRef<any>(null);

  // Reset pending points
  useEffect(() => {
    if (drawMode !== 'trend' && drawMode !== 'fib' && drawMode !== 'fibext' && drawMode !== 'fibfan' && drawMode !== 'pitchfork' && drawMode !== 'rect') {
      setDrawingPoints([]);
    }
  }, [drawMode]);

  const lastCloseRef = useRef(0); // passed from component

  const snapToOHLC = useCallback((price: number, baseCandles: any[], visibleRange?: any): number => {
    if (!baseCandles.length) return price;
    let closest = price;
    let minDiff = Infinity;
    const targetTime = visibleRange?.to ?? baseCandles[baseCandles.length - 1].time;
    const closestCandle = baseCandles.reduce((prev: any, curr: any) =>
      Math.abs(curr.time - targetTime) < Math.abs(prev.time - targetTime) ? curr : prev
    , baseCandles[0]);
    const levels = [closestCandle.open, closestCandle.high, closestCandle.low, closestCandle.close];
    for (const level of levels) {
      const diff = Math.abs(level - price);
      if (diff < minDiff) {
        minDiff = diff;
        closest = level;
      }
    }
    return closest;
  }, []);

  const findDrawingAt = useCallback((time: number, price: number, baseCandles: any[]) => {
    const toleranceTime = 300;
    const tolerancePrice = (baseCandles[baseCandles.length - 1]?.close || 100) * 0.002;
    for (let i = drawings.length - 1; i >= 0; i--) {
      const d = drawings[i];
      if (d.type === 'hline') {
        if (d.price != null && Math.abs(d.price - price) < tolerancePrice) {
          return { id: d.id, type: 'hline' as const, price: d.price };
        }
      } else if (d.points && (d.type === 'trend' || d.type === 'ray' || d.type === 'fib' || d.type === 'rect' || d.type === 'pitchfork')) {
        for (let pi = 0; pi < d.points.length; pi++) {
          const p = d.points[pi];
          if (Math.abs(p.time - time) < toleranceTime && Math.abs(p.price - price) < tolerancePrice) {
            return { id: d.id, pointIndex: pi, type: d.type };
          }
        }
      }
    }
    return null;
  }, [drawings]);

  const clearDrawings = useCallback(() => {
    setDrawings([]);
    setDrawingPoints([]);
    setSelectedDrawingId(null);
  }, [setDrawings]);

  // Editable text support
  const updateDrawingText = useCallback((id: number, newText: string) => {
    setDrawings(prev => prev.map(d => d.id === id ? { ...d, text: newText } : d));
  }, [setDrawings]);

  // Update arbitrary props on a drawing (for future)
  const updateDrawing = useCallback((id: number, patch: Partial<Drawing>) => {
    setDrawings(prev => prev.map(d => d.id === id ? { ...d, ...patch } : d));
  }, [setDrawings]);

  // Mouse handlers - expect to be called with chart context
  const onMouseDown = useCallback((e: React.MouseEvent, baseCandles: any[], chart: any, rect: DOMRect) => {
    if (drawMode !== 'crosshair') return;
    if (!rect || !chart) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    // @ts-ignore - real coordinate APIs for precise drag/selection (lightweight-charts typing)
    const price = (chart.priceScale() as any).coordinateToPrice?.(y) ?? 0;
    // @ts-ignore
    const logical = (chart.timeScale() as any).coordinateToLogical?.(x) ?? 0;
    const range = chart.timeScale().getVisibleRange();
    let approxTime = 0;
    if (range && baseCandles.length) {
      const dataLen = baseCandles.length;
      const idx = Math.floor((logical + 10) * dataLen / 20);
      approxTime = baseCandles[Math.max(0, Math.min(dataLen - 1, Math.floor(idx)))]?.time || 0;
    }
    const hit = findDrawingAt(approxTime, price, baseCandles);
    if (hit) {
      setSelectedDrawingId(hit.id);
      setDragInfo({ ...hit, startX: x, startY: y, startPrice: price });
      setIsDragging(true);
    } else {
      setSelectedDrawingId(null);
    }
  }, [drawMode, findDrawingAt]);

  const onMouseMove = useCallback((e: React.MouseEvent, baseCandles: any[], chart: any, rect: DOMRect) => {
    if (!isDragging || !dragInfo || !rect || !chart) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    // @ts-ignore - real coordinate APIs for precise drag/selection (lightweight-charts typing)
    const priceCoord = (chart.priceScale() as any).coordinateToPrice?.(y) || 0;
    const newPrice = snapToOHLC(priceCoord, baseCandles);
    // @ts-ignore
    const logical = (chart.timeScale() as any).coordinateToLogical?.(x) || 0;
    const range = chart.timeScale().getVisibleRange();
    let newTime = dragInfo.time || 0;
    if (range && baseCandles.length) {
      const idx = Math.floor((logical + 10) * baseCandles.length / 20);
      newTime = baseCandles[Math.max(0, Math.min(baseCandles.length - 1, Math.floor(idx)))]?.time || newTime;
    }
    setDrawings((prev: Drawing[]) => prev.map((d: Drawing) => {
      if (d.id !== dragInfo.id) return d;
      if (d.type === 'hline') {
        return { ...d, price: newPrice };
      } else if (d.points && dragInfo.pointIndex != null) {
        const newPts = [...d.points];
        newPts[dragInfo.pointIndex] = { time: newTime, price: newPrice };
        return { ...d, points: newPts };
      }
      return d;
    }));
  }, [isDragging, dragInfo, snapToOHLC, setDrawings]);

  const onMouseUp = useCallback((onSave?: (drawings: Drawing[]) => void) => {
    if (isDragging) {
      setIsDragging(false);
      setDragInfo(null);
      if (onSave) onSave(drawings);
    }
  }, [isDragging, drawings]);

  const getClickHandler = useCallback((param: any, baseCandles: any[], chart: any, theme: any, snap: any) => {
    if (!param.time) return;
    const getPrice = () => {
      const p = (param.seriesPrices && param.seriesPrices.size > 0)
        ? Array.from(param.seriesPrices.values())[0] as number
        : (baseCandles[baseCandles.length - 1]?.close || 0);
      return snap(p, baseCandles, chart.timeScale().getVisibleRange());
    };
    // ... logic for each mode, similar to before, returning new drawings or updating points
    // For brevity in hook, return action or handle set here
    // We'll keep some logic in component for simplicity, or implement fully
  }, []);

  // For full, we'll implement the full click logic in the hook too.

  const handleChartClick = useCallback((param: any, baseCandles: any[], chart: any, theme: any, snapFn: any, saveFn?: any) => {
    if (!param.time) return;
    const getPrice = () => snapFn(
      (param.seriesPrices && param.seriesPrices.size > 0) ? Array.from(param.seriesPrices.values())[0] as number : (baseCandles[baseCandles.length-1]?.close || 0),
      baseCandles,
      chart.timeScale().getVisibleRange()
    );
    if (drawMode === 'hline') {
      const price = getPrice();
      const newDrawing: Drawing = { id: Date.now(), type: 'hline', price, color: theme.amber };
      setDrawings(prev => [...prev, newDrawing]);
    } else if (drawMode === 'trend' || drawMode === 'ray') {
      const price = getPrice();
      const pt = { time: param.time, price };
      const pts = [...drawingPoints, pt];
      setDrawingPoints(pts);
      if (pts.length === 2) {
        const newDrawing: Drawing = { id: Date.now(), type: drawMode, points: pts, color: drawMode === 'ray' ? theme.cyan : theme.green };
        setDrawings(prev => [...prev, newDrawing]);
        setDrawingPoints([]);
      }
    } else if (drawMode === 'fib' || drawMode === 'fibext' || drawMode === 'fibfan') {
      const price = getPrice();
      const pt = { time: param.time, price };
      const pts = [...drawingPoints, pt];
      setDrawingPoints(pts);
      if (pts.length === 2) {
        const variant = drawMode === 'fibext' ? 'ext' : (drawMode === 'fibfan' ? 'fan' : 'retr');
        const newDrawing: Drawing = { id: Date.now(), type: 'fib', points: pts, color: theme.purple, variant };
        setDrawings(prev => [...prev, newDrawing]);
        setDrawingPoints([]);
      }
    } else if (drawMode === 'rect') {
      const price = getPrice();
      const pt = { time: param.time, price };
      const pts = [...drawingPoints, pt];
      setDrawingPoints(pts);
      if (pts.length === 2) {
        const newDrawing: Drawing = { id: Date.now(), type: 'rect', points: pts, color: theme.red };
        setDrawings(prev => [...prev, newDrawing]);
        setDrawingPoints([]);
      }
    } else if (drawMode === 'pitchfork') {
      const price = getPrice();
      const pt = { time: param.time, price };
      const pts = [...drawingPoints, pt];
      setDrawingPoints(pts);
      if (pts.length === 3) {
        const newDrawing: Drawing = { id: Date.now(), type: 'pitchfork', points: pts, color: '#ff9800' };
        setDrawings(prev => [...prev, newDrawing]);
        setDrawingPoints([]);
      }
    } else if (drawMode === 'text') {
      const price = getPrice();
      const text = prompt('Enter annotation text:') || 'Note';
      const newDrawing: Drawing = { id: Date.now(), type: 'text', time: param.time, price, text, color: theme.text };
      setDrawings(prev => [...prev, newDrawing]);
    }
  }, [drawMode, drawingPoints, setDrawings, setDrawingPoints]);

  return {
    drawings,
    setDrawings,
    drawMode,
    setDrawMode,
    drawingPoints,
    setDrawingPoints,
    selectedDrawingId,
    setSelectedDrawingId,
    isDragging,
    onMouseDown: onMouseDown,
    onMouseMove: onMouseMove,
    onMouseUp: onMouseUp,
    handleChartClick,
    clearDrawings,
    snapToOHLC,
    findDrawingAt,
    updateDrawingText,
    updateDrawing,
  };
}
