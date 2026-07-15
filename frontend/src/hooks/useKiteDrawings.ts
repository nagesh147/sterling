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

  // Undo/redo history: stacks of committed drawings snapshots. Plain refs, not
  // state - nothing needs to re-render off the stacks themselves, only off
  // `drawings` changing (via _setDrawings below). Keeping them as refs avoids
  // ever calling one setState from inside another setState's updater, which
  // React can legitimately flag as "update during render" once several of
  // these fire in the same tick (e.g. holding Ctrl+Z).
  const undoStackRef = useRef<Drawing[][]>([]);
  const redoStackRef = useRef<Drawing[][]>([]);
  // Pre-drag snapshot, captured on mousedown-hit and consumed on mouseup so a
  // whole drag commits as ONE undo entry rather than one per mousemove frame.
  const dragStartSnapshotRef = useRef<Drawing[] | null>(null);
  // Whether the current drag actually moved a point (vs. a plain click-to-select).
  const dragMovedRef = useRef(false);
  // Mirrors `drawings` so undo/redo/setDrawings can read the latest value
  // without needing it in their useCallback deps (keeps them stable).
  const drawingsRef = useRef<Drawing[]>(drawings);
  useEffect(() => { drawingsRef.current = drawings; }, [drawings]);

  // Keep this hook's internal drawings state in sync with the caller-supplied
  // `initialDrawings` whenever ITS identity changes - not just at mount (the
  // `useState(initialDrawings)` above only seeds the very first render). Without
  // this, a caller that swaps in a different `initialDrawings` array later (e.g.
  // a symbol switch loading a different chart's saved drawings, while this same
  // hook instance stays mounted) would leave every mutation below (add/drag/
  // undo/redo) operating on the PREVIOUS symbol's stale snapshot, silently
  // merging its old drawings into the new symbol's saved state on the next edit.
  // Safe to run unconditionally: when the caller instead just echoes back this
  // hook's own last `onChange` output, `initialDrawings` arrives as the same
  // (or an equal-content) array, so this is a no-op re-set.
  useEffect(() => {
    _setDrawings(initialDrawings);
  }, [initialDrawings]);

  // Raw apply: updates state + forwards to the parent's onChange, with NO
  // history bookkeeping. Used internally for the many per-frame updates during
  // a drag (see onMouseMove below) so dragging doesn't spam the undo stack.
  const applyDrawings = useCallback((newDrawings: Drawing[] | ((prev: Drawing[]) => Drawing[])) => {
    _setDrawings(newDrawings);
    if (onChange) {
      const updated = typeof newDrawings === 'function' ? newDrawings(drawingsRef.current) : newDrawings;
      onChange(updated);
    }
  }, [onChange]);

  // Public setter: records the pre-mutation snapshot onto the undo stack (and
  // clears redo) before applying. This is the one used for every discrete,
  // committed action (add/delete/clear/text edit) in this hook and by the
  // consuming component.
  const setDrawings = useCallback((newDrawings: Drawing[] | ((prev: Drawing[]) => Drawing[])) => {
    undoStackRef.current = [...undoStackRef.current, drawingsRef.current];
    redoStackRef.current = [];
    applyDrawings(newDrawings);
  }, [applyDrawings]);

  // Step backward/forward through committed snapshots.
  const undo = useCallback(() => {
    const stack = undoStackRef.current;
    if (stack.length === 0) return;
    const last = stack[stack.length - 1];
    undoStackRef.current = stack.slice(0, -1);
    redoStackRef.current = [...redoStackRef.current, drawingsRef.current];
    applyDrawings(last);
  }, [applyDrawings]);

  const redo = useCallback(() => {
    const stack = redoStackRef.current;
    if (stack.length === 0) return;
    const last = stack[stack.length - 1];
    redoStackRef.current = stack.slice(0, -1);
    undoStackRef.current = [...undoStackRef.current, drawingsRef.current];
    applyDrawings(last);
  }, [applyDrawings]);

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
      dragStartSnapshotRef.current = drawingsRef.current; // pre-drag snapshot for a single undo entry on commit
      dragMovedRef.current = false; // only commit an undo entry if the drag actually moved something
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
    dragMovedRef.current = true;
    applyDrawings((prev: Drawing[]) => prev.map((d: Drawing) => {
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
  }, [isDragging, dragInfo, snapToOHLC, applyDrawings]);

  const onMouseUp = useCallback((onSave?: (drawings: Drawing[]) => void) => {
    if (isDragging) {
      setIsDragging(false);
      setDragInfo(null);
      // Commit the whole drag as a SINGLE undo entry (the pre-drag snapshot),
      // rather than one entry per mousemove frame - and only if something
      // actually moved, so a plain click-to-select doesn't waste an undo step.
      if (dragStartSnapshotRef.current && dragMovedRef.current) {
        undoStackRef.current = [...undoStackRef.current, dragStartSnapshotRef.current];
        redoStackRef.current = [];
      }
      dragStartSnapshotRef.current = null;
      if (onSave) onSave(drawingsRef.current);
    }
  }, [isDragging]);

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
    undo,
    redo,
  };
}
