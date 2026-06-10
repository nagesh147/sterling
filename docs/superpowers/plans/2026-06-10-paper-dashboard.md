# Paper-Book Demo Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A judge-ready, read-only dashboard (Guided + Pro views) that surfaces the research/paper conviction book honestly, with a persistent NOT-LIVE banner and the DSR-0.327 "not deflation-provable → paper-only" verdict front and center.

**Architecture:** One additive read-only FastAPI endpoint (`app/api/v1/endpoints/paper.py`) reads `data/paper/{state.json,trades.csv}` as files (imports no `study.*` — isolation preserved), exposing `/state` `/trades` `/summary`. A React Query hook (`usePaperBook.ts`) feeds a new `PaperResearchTab` (registered in `Dashboard.tsx`) with a Guided/Pro mode toggle. No live-engine logic changes.

**Tech Stack:** FastAPI + pytest (`TestClient` over a minimal app). React + Vite + TS, `@tanstack/react-query`, `lightweight-charts`. FE gate = `tsc` (no FE test runner).

**Run conventions:** backend from `backend/`: `PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_paper_endpoint.py -q`. Frontend from `frontend/`: `npx tsc --noEmit`.

**Honesty invariants (must hold at the end):** (a) `import app.api.v1.endpoints.paper` pulls in no `study` module; (b) backtest-validation numbers are served as static labeled constants, never as a live recompute; (c) no options/Greeks panels; (d) the NOT-LIVE banner is always visible.

---

### Task 1: Backend `/state` + helpers + isolation

**Files:**
- Create: `backend/app/api/v1/endpoints/paper.py`
- Test: `backend/tests/test_paper_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_paper_endpoint.py`:

```python
"""Read-only paper-book demo endpoint — file-backed, isolated from study.*."""
from __future__ import annotations

import csv
import json
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.v1.endpoints.paper as paper_mod
from app.api.v1.endpoints.paper import router as paper_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(paper_mod, "PAPER_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(paper_router, prefix="/api/v1")
    return TestClient(app)


def _write_state(tmp_path):
    state = {
        "total_equity": 889.02, "capital": 500.0, "n_closed": 146,
        "inception": "2025-09-07T00:00:00", "asof": "2026-06-10T08:00:00",
        "realized": {"end": 857.76, "ret": 0.7155, "sharpe": 2.35,
                     "max_dd": -0.2986, "n": 3,
                     "weighted_pnls": [0.10, -0.05, 0.08]},
        "open_positions": [{"symbol": "BTCUSD", "direction": "short",
                            "unrealized_pnl": 0.0375}],
        "breaker": {"peak": 889.02, "drawdown": 0.05, "tripped": False,
                    "threshold": 0.25, "recover": 0.10},
    }
    (tmp_path / "state.json").write_text(json.dumps(state))


def test_state_missing_is_available_false_not_500(client):
    r = client.get("/api/v1/paper/state")
    assert r.status_code == 200
    assert r.json()["available"] is False


def test_state_returns_derived_fields(client, tmp_path):
    _write_state(tmp_path)
    r = client.get("/api/v1/paper/state")
    assert r.status_code == 200
    b = r.json()
    assert b["available"] is True
    assert b["return_pct"] == pytest.approx(77.8, abs=0.1)        # 889.02/500-1
    assert b["buffer_to_trip"] == pytest.approx(20.0, abs=0.1)    # (0.25-0.05)*100
    assert b["tripped"] is False
    # equity_curve = cumprod(1+wp)*capital: 500*1.10=550, *0.95=522.5, *1.08=564.3
    assert b["equity_curve"][0] == pytest.approx(550.0, abs=0.1)
    assert b["equity_curve"][-1] == pytest.approx(564.3, abs=0.2)
    assert b["realized"]["sharpe"] == pytest.approx(2.35)
    assert len(b["open_positions"]) == 1


def test_paper_module_does_not_import_study(client):
    # Isolation invariant: the endpoint reads files, never imports study code.
    assert not any(m == "study" or m.startswith("study.") for m in sys.modules), \
        "paper endpoint must not import any study.* module"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_paper_endpoint.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.v1.endpoints.paper'`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/api/v1/endpoints/paper.py`:

```python
"""Read-only paper-book demo endpoint.

Surfaces the research/paper conviction book (data/paper/*) for the dashboard.
READS FILES ONLY — imports NO study.* module, preserving the 'app never imports
study' isolation invariant. The book is DSR 0.327 < 0.5 (not deflation-provable)
and PAPER-ONLY; this endpoint never executes, mutates, or trades anything.
"""
from __future__ import annotations

import csv
import json
import os

from fastapi import APIRouter

router = APIRouter(prefix="/paper", tags=["paper"])

# Local constant (NOT imported from study, to preserve isolation). Overridable
# for tests. Matches study.paper_trader.PAPER_DIR by convention.
PAPER_DIR = os.environ.get("PAPER_DIR", "data/paper")

# Static backtest-VALIDATION result — labeled constants, never a live recompute.
_VALIDATION = {
    "dsr": 0.327,
    "oos_sharpe": 1.57,
    "oos_return_pct": 75.8,
    "is_oos_corr": 0.38,
    "provable": False,
    "verdict": ("Real out-of-sample edge (Sharpe 1.57); DSR 0.327 < 0.5 — "
                "not deflation-provable. Research/paper only, never live money."),
    "provenance": ("validated 2026-06-10; docs/funding_sleeve_result.md + "
                   "docs/regime_book_before_after.md"),
}


def _equity_curve(weighted_pnls, capital):
    """Realized (closed-trade) equity progression: cumprod(1+wp)*capital."""
    eq, v = [], float(capital)
    for p in weighted_pnls or []:
        v *= (1.0 + float(p))
        eq.append(round(v, 2))
    return eq


@router.get("/state")
def paper_state():
    """Live paper-book state (read from data/paper/state.json) + derived fields.
    Missing/unreadable file → {available: false} with 200 (demo-safe)."""
    path = os.path.join(PAPER_DIR, "state.json")
    if not os.path.exists(path):
        return {"available": False,
                "reason": "no paper state — run `python -m study.paper_trader`"}
    try:
        with open(path) as f:
            d = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {"available": False, "reason": f"unreadable state: {e}"}

    capital = float(d.get("capital", 500.0)) or 500.0
    realized = d.get("realized", {}) or {}
    breaker = d.get("breaker", {}) or {}
    total_equity = float(d.get("total_equity", realized.get("end", capital)))
    return {
        "available": True,
        "total_equity": round(total_equity, 2),
        "return_pct": round((total_equity / capital - 1.0) * 100, 2),
        "realized": {k: realized.get(k) for k in ("end", "ret", "sharpe", "max_dd", "n")},
        "equity_curve": _equity_curve(realized.get("weighted_pnls"), capital),
        "open_positions": d.get("open_positions", []),
        "breaker": breaker,
        "buffer_to_trip": round((float(breaker.get("threshold", 0.0))
                                 - float(breaker.get("drawdown", 0.0))) * 100, 2),
        "tripped": bool(breaker.get("tripped", False)),
        "asof": d.get("asof"),
        "inception": d.get("inception"),
        "n_closed": d.get("n_closed", 0),
        "capital": capital,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_paper_endpoint.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/app/api/v1/endpoints/paper.py backend/tests/test_paper_endpoint.py
git commit -m "feat(api): read-only paper-book /state endpoint (isolated from study)

Reads data/paper/state.json as a file (no study import), returns live equity +
derived return_pct/equity_curve/buffer_to_trip. Missing file -> available:false
(200, demo-safe). Isolation asserted by test.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Backend `/trades` + `/summary`

**Files:**
- Modify: `backend/app/api/v1/endpoints/paper.py`
- Test: `backend/tests/test_paper_endpoint.py`

- [ ] **Step 1: Write the failing test (append)**

```python
def _write_trades(tmp_path):
    rows = [
        {"entry_time": "2026-06-01T00:00:00", "exit_time": "2026-06-02T00:00:00",
         "symbol": "BTCUSD", "sleeve": "trend", "direction": "short",
         "status": "closed", "pnl_pct": "0.031", "stop_dist_pct": "0.05"},
        {"entry_time": "2026-06-03T00:00:00", "exit_time": "2026-06-04T00:00:00",
         "symbol": "ETHUSD", "sleeve": "mr", "direction": "long",
         "status": "closed", "pnl_pct": "-0.012", "stop_dist_pct": "0.04"},
    ]
    with open(tmp_path / "trades.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def test_trades_returns_ledger_with_numeric_pnl(client, tmp_path):
    _write_trades(tmp_path)
    r = client.get("/api/v1/paper/trades")
    assert r.status_code == 200
    b = r.json()
    assert b["available"] is True and b["n"] == 2
    assert b["trades"][0]["pnl_pct"] == pytest.approx(0.031)   # coerced to float
    assert b["trades"][0]["symbol"] == "BTCUSD"


def test_trades_missing_is_available_false(client):
    r = client.get("/api/v1/paper/trades")
    assert r.status_code == 200
    assert r.json()["available"] is False
    assert r.json()["trades"] == []


def test_summary_is_static_validation_not_provable(client):
    r = client.get("/api/v1/paper/summary")
    assert r.status_code == 200
    b = r.json()
    assert b["dsr"] == 0.327
    assert b["provable"] is False
    assert "not deflation-provable" in b["verdict"]
    assert "docs/" in b["provenance"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_paper_endpoint.py -k "trades or summary" -q`
Expected: FAIL — 404 (routes not defined yet).

- [ ] **Step 3: Add the implementation (append to paper.py)**

```python
@router.get("/trades")
def paper_trades():
    """Closed-trade ledger (read from data/paper/trades.csv). pnl_pct and
    stop_dist_pct coerced to float; missing file → {available: false, trades: []}."""
    path = os.path.join(PAPER_DIR, "trades.csv")
    if not os.path.exists(path):
        return {"available": False, "trades": [], "n": 0}
    try:
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as e:
        return {"available": False, "trades": [], "n": 0, "reason": str(e)}
    for r in rows:
        for k in ("pnl_pct", "stop_dist_pct"):
            try:
                r[k] = float(r[k])
            except (TypeError, ValueError, KeyError):
                pass
    return {"available": True, "trades": rows, "n": len(rows)}


@router.get("/summary")
def paper_summary():
    """Static backtest-validation block (provenance-labeled; NOT a live recompute)."""
    return {"available": True, **_VALIDATION}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_paper_endpoint.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/app/api/v1/endpoints/paper.py backend/tests/test_paper_endpoint.py
git commit -m "feat(api): paper /trades ledger + /summary static validation block

/trades parses trades.csv (pnl coerced to float); /summary serves the
backtest-validation result (DSR 0.327, provable:false) as labeled constants.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Wire the router into `main.py`

**Files:**
- Modify: `backend/main.py` (import block ~line 41; include block ~line 1674)

- [ ] **Step 1: Add the import**

After the line `from app.api.v1.endpoints.sterling_v2 import router as sterling_v2_router` (~line 41), add:

```python
from app.api.v1.endpoints.paper import router as paper_router
```

- [ ] **Step 2: Add the include**

After the existing `app.include_router(directional_router, prefix="/api/v1")` group (the block of `app.include_router(..., prefix="/api/v1")` calls starting ~line 1674), add a line consistent with the others:

```python
    app.include_router(paper_router, prefix="/api/v1")
```

- [ ] **Step 3: Verify the app imports and the routes are mounted**

Run:
```bash
cd backend && PYTHONWARNINGS=ignore .venv/bin/python -c "
from main import create_app
app = create_app()
paths = [r.path for r in app.routes]
assert '/api/v1/paper/state' in paths, 'state route missing'
assert '/api/v1/paper/trades' in paths and '/api/v1/paper/summary' in paths
print('paper routes mounted OK')
"
```
Expected: `paper routes mounted OK`.

- [ ] **Step 4: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/main.py
git commit -m "feat(api): mount paper-book router at /api/v1/paper

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Frontend hook `usePaperBook.ts`

**Files:**
- Create: `frontend/src/hooks/usePaperBook.ts`

- [ ] **Step 1: Write the hook**

Create `frontend/src/hooks/usePaperBook.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { api } from '../utils/api';

export interface PaperPosition {
  symbol: string;
  sleeve?: string;
  direction: string;
  entry_time?: string;
  entry_price?: number;
  sl?: number;
  tp?: number;
  mtm_price?: number;
  unrealized_pnl?: number;
  stop_dist_pct?: number;
  weight?: number;
}

export interface PaperState {
  available: boolean;
  reason?: string;
  total_equity?: number;
  return_pct?: number;
  realized?: { end?: number; ret?: number; sharpe?: number; max_dd?: number; n?: number };
  equity_curve?: number[];
  open_positions?: PaperPosition[];
  breaker?: { peak?: number; drawdown?: number; tripped?: boolean; threshold?: number; recover?: number };
  buffer_to_trip?: number;
  tripped?: boolean;
  asof?: string;
  inception?: string;
  n_closed?: number;
  capital?: number;
}

export interface PaperTrade {
  entry_time: string;
  exit_time: string;
  symbol: string;
  sleeve: string;
  direction: string;
  status: string;
  pnl_pct: number;
  stop_dist_pct: number;
}

export interface PaperTrades {
  available: boolean;
  trades: PaperTrade[];
  n: number;
}

export interface PaperSummary {
  available: boolean;
  dsr: number;
  oos_sharpe: number;
  oos_return_pct: number;
  is_oos_corr: number;
  provable: boolean;
  verdict: string;
  provenance: string;
}

export function usePaperState() {
  return useQuery<PaperState>({
    queryKey: ['paper', 'state'],
    queryFn: () => api<PaperState>('/api/v1/paper/state'),
  });
}

export function usePaperTrades() {
  return useQuery<PaperTrades>({
    queryKey: ['paper', 'trades'],
    queryFn: () => api<PaperTrades>('/api/v1/paper/trades'),
  });
}

export function usePaperSummary() {
  return useQuery<PaperSummary>({
    queryKey: ['paper', 'summary'],
    queryFn: () => api<PaperSummary>('/api/v1/paper/summary'),
  });
}
```

- [ ] **Step 2: Verify the api helper signature matches**

Run: `cd frontend && grep -n "export" src/utils/api.ts | head`
Expected: confirms `api` is the exported fetch helper. If the export is `export async function api<T>(path: string, options?: RequestInit): Promise<T>` (or a default export), adjust the import/usage above to match exactly (e.g., `import api from '../utils/api'`). Fix the hook to the real signature before continuing.

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors referencing `usePaperBook.ts`.

- [ ] **Step 4: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add frontend/src/hooks/usePaperBook.ts
git commit -m "feat(ui): usePaperBook React Query hooks (state/trades/summary)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Frontend `PaperEquityCurve.tsx` (chart)

**Files:**
- Create: `frontend/src/components/paper/PaperEquityCurve.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/src/components/paper/PaperEquityCurve.tsx` (patterned on `src/components/EquityCurve.tsx`'s lightweight-charts setup, but prop-driven; x is trade sequence with date labels hidden, since the realized curve is per-trade, not calendar-spaced):

```typescript
import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ColorType, LineSeries } from 'lightweight-charts';

export function PaperEquityCurve({ points, height = 220 }: {
  points: number[]; height?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: 'transparent' },
                textColor: 'var(--text-dim)' },
      grid: { vertLines: { visible: false }, horzLines: { color: 'var(--border)' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: false, secondsVisible: false },
      width: containerRef.current.clientWidth,
      height,
    });
    chartRef.current = chart;
    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    ro.observe(containerRef.current);
    return () => { ro.disconnect(); chart.remove(); };
  }, [height]);

  useEffect(() => {
    if (!chartRef.current || !points?.length) return;
    const up = points[points.length - 1] >= points[0];
    const series = chartRef.current.addSeries(LineSeries, {
      color: up ? '#22c55e' : '#ef4444',
      lineWidth: 2, lastValueVisible: true, priceLineVisible: false,
    });
    // x = trade sequence (synthetic daily spacing); date axis hidden above.
    const t0 = 1700000000;
    series.setData(points.map((value, i) => ({ time: (t0 + i * 86400) as any, value })));
    chartRef.current.timeScale().fitContent();
    return () => { chartRef.current?.removeSeries(series); };
  }, [points]);

  return <div ref={containerRef} style={{ width: '100%' }} />;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors referencing `PaperEquityCurve.tsx`. (If `addSeries(LineSeries, …)` differs in the installed lightweight-charts v5 API, mirror exactly what `src/components/EquityCurve.tsx` does — it is known-good against the installed version.)

- [ ] **Step 3: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add frontend/src/components/paper/PaperEquityCurve.tsx
git commit -m "feat(ui): PaperEquityCurve (prop-driven lightweight-charts line)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Frontend `PaperResearchTab.tsx` (Guided + Pro)

**Files:**
- Create: `frontend/src/components/paper/PaperResearchTab.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/src/components/paper/PaperResearchTab.tsx`:

```typescript
import React, { useState } from 'react';
import { usePaperState, usePaperTrades, usePaperSummary, PaperPosition } from '../../hooks/usePaperBook';
import { PaperEquityCurve } from './PaperEquityCurve';

const box: React.CSSProperties = {
  border: '1px solid var(--border)', borderRadius: 6, padding: 16, marginBottom: 16,
};
const dim: React.CSSProperties = { color: 'var(--text-dim)', fontSize: 11, letterSpacing: '0.08em' };
const pct = (x?: number) => (x == null ? '—' : `${(x * 100).toFixed(2)}%`);
const usd = (x?: number) => (x == null ? '—' : `$${x.toLocaleString(undefined, { maximumFractionDigits: 2 })}`);

function NotLiveBanner() {
  return (
    <div style={{ background: 'var(--accent)18', border: '1px solid var(--accent)',
                  borderRadius: 6, padding: '8px 14px', marginBottom: 16,
                  fontSize: 11, letterSpacing: '0.12em', fontWeight: 600,
                  color: 'var(--accent)' }}>
      RESEARCH · PAPER · NOT LIVE MONEY — DSR 0.327 &lt; 0.5, not deflation-provable
    </div>
  );
}

function PositionsTable({ positions }: { positions: PaperPosition[] }) {
  if (!positions?.length) return <div style={dim}>No open positions.</div>;
  return (
    <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
      <thead>
        <tr style={dim}>
          {['SYMBOL', 'SLEEVE', 'DIR', 'ENTRY', 'SL', 'TP', 'UNREAL'].map(h => (
            <th key={h} style={{ textAlign: 'left', padding: '4px 8px' }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {positions.map((p, i) => (
          <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
            <td style={{ padding: '4px 8px' }}>{p.symbol}</td>
            <td style={{ padding: '4px 8px' }}>{p.sleeve ?? '—'}</td>
            <td style={{ padding: '4px 8px',
                         color: p.direction === 'short' ? '#ef4444' : '#22c55e' }}>
              {p.direction}</td>
            <td style={{ padding: '4px 8px' }}>{usd(p.entry_price)}</td>
            <td style={{ padding: '4px 8px' }}>{usd(p.sl)}</td>
            <td style={{ padding: '4px 8px' }}>{usd(p.tp)}</td>
            <td style={{ padding: '4px 8px',
                         color: (p.unrealized_pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444' }}>
              {pct(p.unrealized_pnl)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PaperResearchTab() {
  const [mode, setMode] = useState<'guided' | 'pro'>('guided');
  const state = usePaperState();
  const trades = usePaperTrades();
  const summary = usePaperSummary();

  const s = state.data;
  if (state.isLoading) return <div style={dim}>Loading paper book…</div>;
  if (!s?.available) {
    return (
      <div>
        <NotLiveBanner />
        <div style={box}>Paper book not generated yet. Run
          <code> python -m study.paper_trader</code>{s?.reason ? ` (${s.reason})` : ''}.</div>
      </div>
    );
  }

  const sum = summary.data;
  const upColor = (s.return_pct ?? 0) >= 0 ? '#22c55e' : '#ef4444';

  return (
    <div>
      <NotLiveBanner />

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['guided', 'pro'] as const).map(m => (
          <button key={m} onClick={() => setMode(m)} style={{
            background: 'none', border: '1px solid var(--border)', borderRadius: 4,
            cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, padding: '6px 14px',
            letterSpacing: '0.08em', fontWeight: mode === m ? 600 : 400,
            color: mode === m ? 'var(--text-primary)' : 'var(--text-dim)',
            borderColor: mode === m ? 'var(--accent)' : 'var(--border)',
          }}>{m.toUpperCase()}</button>
        ))}
        <button onClick={() => { state.refetch(); trades.refetch(); }} style={{
          marginLeft: 'auto', background: 'none', border: '1px solid var(--border)',
          borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
          padding: '6px 14px', color: 'var(--text-dim)' }}>↻ REFRESH</button>
      </div>

      {/* Hero — both modes */}
      <div style={{ ...box, display: 'flex', alignItems: 'baseline', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: upColor }}>
          {usd(s.capital)} → {usd(s.total_equity)}
        </div>
        <div style={{ fontSize: 18, color: upColor }}>
          {(s.return_pct ?? 0) >= 0 ? '+' : ''}{s.return_pct}%
        </div>
        <div style={dim}>since {s.inception?.slice(0, 10)} · {s.n_closed} closed</div>
      </div>

      {/* Verdict — both modes, front and center */}
      {sum && (
        <div style={{ ...box, borderColor: 'var(--accent)' }}>
          <div style={dim}>HONEST VERDICT</div>
          <div style={{ fontSize: 13, marginTop: 6 }}>{sum.verdict}</div>
          <div style={{ ...dim, marginTop: 6 }}>{sum.provenance}</div>
        </div>
      )}

      {/* Kill-switch + live paper stats — both modes */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ ...box, flex: 1, minWidth: 200 }}>
          <div style={dim}>KILL-SWITCH</div>
          <div style={{ fontSize: 16, marginTop: 6,
                        color: s.tripped ? '#ef4444' : '#22c55e' }}>
            {s.tripped ? 'TRIPPED · FLAT' : `ARMED · ${s.buffer_to_trip}% buffer`}
          </div>
          <div style={{ ...dim, marginTop: 4 }}>
            drawdown {pct(s.breaker?.drawdown)} / trip at {pct(s.breaker?.threshold)}
          </div>
        </div>
        <div style={{ ...box, flex: 1, minWidth: 200 }}>
          <div style={dim}>LIVE PAPER-FORWARD</div>
          <div style={{ fontSize: 13, marginTop: 6 }}>
            Sharpe {s.realized?.sharpe?.toFixed(2)} · ret {pct(s.realized?.ret)} ·
            maxDD {pct(s.realized?.max_dd)} · n {s.realized?.n}
          </div>
        </div>
      </div>

      <div style={box}>
        <div style={dim}>OPEN POSITIONS</div>
        <div style={{ marginTop: 8 }}><PositionsTable positions={s.open_positions ?? []} /></div>
      </div>

      {/* Pro-only: equity curve + validation panel + ledger */}
      {mode === 'pro' && (
        <>
          <div style={box}>
            <div style={dim}>REALIZED (CLOSED) EQUITY · by trade #
              <span style={{ marginLeft: 8 }}>→ +open unrealized = {usd(s.total_equity)}</span>
            </div>
            <div style={{ marginTop: 8 }}><PaperEquityCurve points={s.equity_curve ?? []} /></div>
          </div>

          {sum && (
            <div style={box}>
              <div style={dim}>BACKTEST VALIDATION (static, out-of-sample)</div>
              <div style={{ fontSize: 13, marginTop: 6 }}>
                OOS return +{sum.oos_return_pct}% · Sharpe {sum.oos_sharpe} ·
                DSR {sum.dsr} ({sum.provable ? 'provable' : 'NOT provable, <0.5'}) ·
                IS→OOS corr +{sum.is_oos_corr}
              </div>
            </div>
          )}

          <div style={box}>
            <div style={dim}>CLOSED-TRADE LEDGER ({trades.data?.n ?? 0})</div>
            <div style={{ marginTop: 8, maxHeight: 320, overflow: 'auto' }}>
              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                <thead><tr style={dim}>
                  {['EXIT', 'SYMBOL', 'SLEEVE', 'DIR', 'PNL%'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '4px 8px' }}>{h}</th>))}
                </tr></thead>
                <tbody>
                  {(trades.data?.trades ?? []).slice().reverse().map((tr, i) => (
                    <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: '4px 8px' }}>{tr.exit_time?.slice(0, 10)}</td>
                      <td style={{ padding: '4px 8px' }}>{tr.symbol}</td>
                      <td style={{ padding: '4px 8px' }}>{tr.sleeve}</td>
                      <td style={{ padding: '4px 8px' }}>{tr.direction}</td>
                      <td style={{ padding: '4px 8px',
                                   color: tr.pnl_pct >= 0 ? '#22c55e' : '#ef4444' }}>
                        {(tr.pnl_pct * 100).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors referencing `PaperResearchTab.tsx`. Fix any type mismatches (e.g., unused imports) inline.

- [ ] **Step 3: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add frontend/src/components/paper/PaperResearchTab.tsx
git commit -m "feat(ui): PaperResearchTab — Guided + Pro views over the paper book

NOT-LIVE banner, honest verdict + provenance, hero equity, kill-switch buffer,
live paper-forward stats, open positions; Pro adds equity curve, validation
panel, closed-trade ledger. No options/Greeks chrome.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Register the tab in `Dashboard.tsx`

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Add `'paper'` to the `Tab` union (line 60)**

Change:
```typescript
type Tab = 'analysis' | 'charts' | 'chain' | 'account' | 'alerts' | 'backtest' | 'positions' | 'watchlist' | 'config';
```
to:
```typescript
type Tab = 'analysis' | 'charts' | 'chain' | 'account' | 'alerts' | 'backtest' | 'positions' | 'watchlist' | 'config' | 'paper';
```

- [ ] **Step 2: Add the TABS entry and TAB_KEYS mapping (key `0`, which is free)**

In `const TABS`, add as the last entry:
```typescript
  ['paper',     'PAPER RESEARCH', '0'],
```
In `const TAB_KEYS`, add:
```typescript
  '0': 'paper',
```

- [ ] **Step 3: Add the import (top of file, with the other component imports)**

```typescript
import { PaperResearchTab } from '../components/paper/PaperResearchTab';
```

- [ ] **Step 4: Add the render branch**

After the `{activeTab === 'config' && ( … )}` block, add:
```typescript
          {activeTab === 'paper' && (
            <PaperResearchTab />
          )}
```

- [ ] **Step 5: Type-check the whole frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean (no errors). Fix any inline.

- [ ] **Step 6: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat(ui): register PAPER RESEARCH tab (key 0) in Dashboard

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Final verification

- [ ] **Step 1: Backend — paper tests + no regression on adjacent suites**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_paper_endpoint.py tests/test_paper_trader.py tests/test_paper_safety.py -q`
Expected: all green.

- [ ] **Step 2: Isolation — app does not import study via the paper endpoint**

Run:
```bash
cd backend && PYTHONWARNINGS=ignore .venv/bin/python -c "
import sys
import app.api.v1.endpoints.paper  # noqa
leaked = [m for m in sys.modules if m == 'study' or m.startswith('study.')]
assert not leaked, f'LEAK: {leaked}'
print('isolation OK — paper endpoint imports no study module')
"
```
Expected: `isolation OK …`.

- [ ] **Step 3: Live endpoint smoke against the real paper book**

Run:
```bash
cd backend && PYTHONWARNINGS=ignore .venv/bin/python -c "
from fastapi.testclient import TestClient
from main import create_app
c = TestClient(create_app())
st = c.get('/api/v1/paper/state').json()
print('state.available =', st.get('available'), '| equity =', st.get('total_equity'),
      '| return% =', st.get('return_pct'), '| buffer =', st.get('buffer_to_trip'))
print('summary.dsr =', c.get('/api/v1/paper/summary').json().get('dsr'))
print('trades.n =', c.get('/api/v1/paper/trades').json().get('n'))
"
```
Expected: `available True`, equity ≈ 889, return% ≈ 77.8, dsr 0.327, trades.n > 0.

- [ ] **Step 4: Frontend type-check (the FE gate)**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 5: Report** the verification output to the user and (optionally) offer to launch the app (backend + `npm run dev`) for a visual confirmation of the Guided/Pro views.

---

## Self-review notes

- **Spec coverage:** `/state`+`/trades`+`/summary` (T1–T2), isolation invariant (T1 test + T8), router wiring (T3), hook (T4), equity curve reuse of lightweight-charts (T5), Guided+Pro + NOT-LIVE banner + verdict + no-options (T6), tab registration (T7), validation incl. live-smoke + tsc (T8). Backtest-validation-as-static-constants and live-paper-from-state separation: T2 `_VALIDATION` + T6 two distinct panels. All spec sections mapped.
- **Placeholder scan:** every code/test step is complete; the one runtime caveat (lightweight-charts v5 `addSeries` API and the `api` helper signature) is handled by explicit "mirror the known-good existing file / adjust to the real export" steps (T4 Step 2, T5 Step 2), not left vague.
- **Type consistency:** endpoint keys (`available, total_equity, return_pct, realized, equity_curve, open_positions, breaker, buffer_to_trip, tripped, asof, inception, n_closed, capital`) match the `PaperState` interface (T4) and the tab's usage (T6); `/summary` keys (`dsr, oos_sharpe, oos_return_pct, is_oos_corr, provable, verdict, provenance`) match `PaperSummary` + T6; `/trades` rows match `PaperTrade`.
```
