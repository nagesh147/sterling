import React, { useEffect, useMemo, useState } from 'react';
import { k } from '../../styles/kiteUI';
import { forecastDay, forecastMonth, liveBoard, liveNow } from '../../lib/astro/engine';
import { lastCompletedSessionIso, nearestOpenIso, shiftSessionIso } from '../../lib/astro/holidays';
import { barsFromOhlcv, gradeSlot, summariseTape, type SlotGrade } from '../../lib/astro/tape';
import { formatIstDate, formatIstIsoDate, getIstParts, minutesOfDay, utcFromIstParts } from '../../lib/astro/time';
import { UNDERLYINGS, WEEKDAYS, type GapKind, type IndexPlay, type LiveNow, type TradeAction, type TradeSide, type Underlying, type WindowSlot } from '../../lib/astro/types';
import { useCandles } from '../../hooks/useCandles';
import { MonthHeat } from './astro/MonthHeat';
import { NowBoard } from './astro/NowBoard';
import { PlaybookNotes, PlaybookStrip } from './astro/PlaybookBoard';
import { SessionStrip } from './astro/SessionStrip';

type Tab = 'timings' | 'thirty' | 'month';

function sessionIso(): string {
  return lastCompletedSessionIso(new Date());
}

function isoToDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return utcFromIstParts(y, m, d, 9, 0, 0);
}

function gapColor(kind: GapKind): string {
  if (kind === 'up') return 'var(--ko-ce)';
  if (kind === 'down') return 'var(--ko-pe)';
  return 'var(--k-amber)';
}

function actionColor(action: TradeAction, side: TradeSide): string {
  if (action === 'AVOID' || action === 'WAIT') return 'var(--k-dim)';
  if (side === 'CE') return 'var(--ko-ce)';
  if (side === 'PE') return 'var(--ko-pe)';
  return 'var(--k-amber)';
}

function underlyingLabel(id: Underlying): string {
  return UNDERLYINGS.find((u) => u.id === id)?.label ?? id;
}

const UNDER_SHORT: { id: Underlying; short: string }[] = [
  { id: 'NIFTY', short: 'Nifty' },
  { id: 'BANKNIFTY', short: 'Bank' },
  { id: 'FINNIFTY', short: 'Fin' },
  { id: 'SENSEX', short: 'Sensex' },
  { id: 'MIDCPNIFTY', short: 'Midcap' },
];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function fmtNavDay(iso: string): string {
  const p = getIstParts(isoToDate(iso));
  return `${WEEKDAYS[p.weekday].slice(0, 3)}, ${p.day} ${MONTHS[p.month - 1]}`;
}

function sideClass(side: WindowSlot['side']): string {
  if (side === 'CE') return 'ko-pill ko-pill-ce';
  if (side === 'PE') return 'ko-pill ko-pill-pe';
  return 'ko-pill ko-pill-wait';
}

function sideLabel(side: WindowSlot['side']): string {
  if (side === 'CE') return 'CE';
  if (side === 'PE') return 'PE';
  if (side === 'BOTH') return 'BOTH';
  return 'WAIT';
}

function productClass(product: string): string {
  if (product === 'MIS') return 'ko-prod ko-prod-mis';
  if (product === 'NRML') return 'ko-prod ko-prod-nrml';
  return 'ko-prod ko-prod-other';
}

function gradeClass(kind: SlotGrade['kind']): string {
  if (kind === 'HIT') return 'ko-st ko-st-hit';
  if (kind === 'MISS') return 'ko-st ko-st-miss';
  if (kind === 'LIVE') return 'ko-st ko-st-live';
  return 'ko-st ko-st-sit';
}

const CSS = `
.kite-astro{--ko-ce:#26a69a;--ko-pe:#ef5350;display:flex;flex-direction:column;height:100%;min-height:100%;background:var(--k-bg);color:var(--k-text);font-family:${k.fontFamily};font-size:14px}
html[data-theme="dark"] .kite-astro,.dark .kite-astro,[data-theme="dark"] .kite-astro{--ko-ce:#089981;--ko-pe:#f23645}
.kite-astro *{box-sizing:border-box}
.ko-head{padding:0 32px;border-bottom:1px solid var(--k-surface-hover);margin-top:12px}
.ko-title-row{display:flex;align-items:center;gap:16px;margin:0 0 4px;min-height:32px}
.ko-title-row h2{margin:0;font-size:24px;font-weight:400;color:var(--k-text);flex:1}
.ko-date{display:flex;align-items:center;gap:4px;flex-shrink:0}
.ko-date-btn{width:36px;height:36px;border:0;background:none;color:var(--k-text);font-size:22px;line-height:1;display:inline-flex;align-items:center;justify-content:center;padding:0;cursor:pointer;font-family:inherit}
.ko-date-btn:hover{color:var(--k-orange)}
.ko-date-value{position:relative;min-width:118px;height:36px;display:inline-flex;align-items:center;justify-content:center;font-size:14px;color:var(--k-text);cursor:pointer;font-variant-numeric:tabular-nums}
.ko-date-value:hover{color:var(--k-orange)}
.ko-date-value input[type=date]{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%;border:0;background:transparent}
.ko-date .ko-link{margin-left:8px;height:36px;display:inline-flex;align-items:center}
.ko-date .ko-link[data-on="true"]{color:var(--k-orange);font-weight:500;text-decoration:none}
.ko-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.ko-tools select,.ko-tools input[type=date]{height:32px;border:1px solid var(--k-border);background:var(--k-bg);color:var(--k-text);font-size:13px;padding:0 8px;border-radius:2px;font-family:inherit}
.ko-link{border:0;background:none;color:var(--k-blue-kite);font-size:13px;padding:0;cursor:pointer;font-family:inherit}
.ko-link:hover{text-decoration:underline}
.ko-tabs-row{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:-1px}
.ko-tabs{display:flex;gap:32px;overflow-x:auto;min-width:0}
.ko-tabs button{padding:0 0 12px;border:0;background:none;color:var(--k-text);font-size:14px;font-weight:400;border-bottom:2px solid transparent;white-space:nowrap;cursor:pointer;font-family:inherit;transition:color .2s}
.ko-tabs button[data-on="true"]{color:var(--k-orange);border-bottom-color:var(--k-orange)}
.ko-ins{display:flex;align-items:center;gap:16px;overflow-x:auto;padding-bottom:12px;flex-shrink:0}
.ko-ins button{border:0;background:none;padding:0;font-size:13px;color:var(--k-text);white-space:nowrap;cursor:pointer;font-family:inherit}
.ko-ins button:hover{color:var(--k-orange)}
.ko-ins button[data-on="true"]{color:var(--k-orange);font-weight:500}
.ko-ins-side{margin-left:5px;font-size:10px;font-weight:500}
.ko-now-board{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:8px;font-size:12px}
.ko-table tbody tr[data-live="true"]{box-shadow:inset 2px 0 0 var(--k-orange)}
.ko-body{flex:1;overflow:auto;padding:20px 32px 40px}
.ko-sub{margin:0 0 16px;font-size:13px;color:var(--k-dim);line-height:1.5}
.ko-notes{margin:0 0 16px;padding:0 0 0 18px;font-size:13px;line-height:1.55;color:var(--k-text)}
.ko-notes li{margin:4px 0}
.ko-scroll{overflow-x:auto}
.ko-table{width:100%;border-collapse:collapse;text-align:left}
.ko-wide{min-width:720px}
.ko-table th{padding:12px 16px;font-size:12px;font-weight:400;color:var(--k-dim);border-bottom:1px solid var(--k-surface-hover);background:var(--k-bg);white-space:nowrap}
.ko-table td{padding:12px 16px;font-size:13px;color:var(--k-text);border-bottom:1px solid var(--k-surface-hover);vertical-align:middle}
.ko-wide td:nth-child(1),.ko-wide td:nth-child(2),.ko-wide td:nth-child(4),.ko-wide td:nth-child(6){white-space:nowrap}
.ko-table tbody tr{cursor:pointer}
.ko-table tbody tr:hover{background:var(--k-surface-2)}
.ko-table tbody tr[data-on="true"]{background:var(--k-surface-2)}
.ko-expand td{padding:8px 16px 16px;font-size:13px;line-height:1.5;cursor:default;background:var(--k-surface-2);white-space:normal}
.ko-pill{display:inline-block;padding:2px 6px;border-radius:3px;font-size:11px;line-height:1.3}
.ko-pill-ce{color:var(--ko-ce);background:color-mix(in srgb,var(--ko-ce) 12%,transparent)}
.ko-pill-pe{color:var(--ko-pe);background:color-mix(in srgb,var(--ko-pe) 12%,transparent)}
.ko-pill-wait{color:var(--k-dim);background:rgba(155,155,155,.1)}
.ko-st{display:inline-block;padding:2px 6px;border-radius:3px;font-size:11px}
.ko-st-hit{color:var(--ko-ce);background:color-mix(in srgb,var(--ko-ce) 12%,transparent)}
.ko-st-miss{color:var(--ko-pe);background:color-mix(in srgb,var(--ko-pe) 12%,transparent)}
.ko-st-live{color:#f57c00;background:rgba(255,152,0,.1)}
.ko-st-sit{color:var(--k-dim);background:rgba(155,155,155,.1)}
.ko-tag{display:inline-block;margin-left:8px;font-size:9px;color:var(--k-dim);background:var(--k-surface-hover);padding:1px 4px;border-radius:2px;vertical-align:middle}
.ko-prod{display:inline-block;padding:2px 7px;border-radius:2px;font-size:10px;font-weight:500}
.ko-prod-mis{color:var(--k-blue-kite);background:rgba(56,126,209,.1)}
.ko-prod-nrml{color:#c856a2;background:rgba(200,86,162,.1)}
.ko-prod-other{color:var(--k-dim);background:var(--k-surface-hover)}
.ko-foot{display:flex;justify-content:flex-end;flex-wrap:wrap;gap:24px;padding:13px 16px;border-top:1px solid var(--k-border);font-size:12px}
.ko-foot .lbl{color:var(--k-dim);margin-right:7px}
.text-up{color:var(--ko-ce)}.text-down{color:var(--ko-pe)}.text-warn{color:var(--k-amber)}.text-ce{color:var(--ko-ce)}.text-pe{color:var(--ko-pe)}.text-muted{color:var(--k-dim)}.text-faint{color:var(--k-dim)}.text-ink{color:var(--k-text)}
.ko-strip{margin:0 0 18px}
.ko-strip svg{width:100%;height:auto;display:block}
.ko-strip g{cursor:pointer}
.ko-strip-tapebg{fill:var(--k-surface-2)}
.ko-strip-ce{fill:var(--ko-ce)}.ko-strip-pe{fill:var(--ko-pe)}.ko-strip-both{fill:var(--k-amber)}.ko-strip-wait{fill:#d6d6d6}.ko-strip-avoid{fill:#bdbdbd}
.ko-strip-upline{stroke:var(--ko-ce);fill:none}.ko-strip-downline{stroke:var(--ko-pe);fill:none}
.ko-strip-tick{stroke:var(--k-border);stroke-width:1}
.ko-strip-now{stroke:var(--k-orange);stroke-width:1.2}
.ko-strip-lbl,.ko-strip-hora,.ko-strip-empty{fill:var(--k-dim);font-size:10px;font-family:inherit}
.ko-strip-hora{font-size:9px}
.ko-strip-leg{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:var(--k-dim);margin-top:8px;align-items:center}
.ko-strip-leg i{display:inline-block;width:8px;height:8px;margin-right:5px;border-radius:1px}
.ko-swatch-ce{background:var(--ko-ce)}.ko-swatch-pe{background:var(--ko-pe)}.ko-swatch-both{background:var(--k-amber)}.ko-swatch-wait{background:#d6d6d6}
.ko-mix{display:flex;height:4px;margin-top:8px;background:var(--k-surface-hover)}
.ko-mix-ce{background:var(--ko-ce)}.ko-mix-pe{background:var(--ko-pe)}.ko-mix-both{background:var(--k-amber)}.ko-mix-wait{background:#d6d6d6}
.ko-kv{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--k-border);margin:0 0 16px}
.ko-kv>div{padding:10px 14px;border-right:1px solid var(--k-surface-hover);border-bottom:1px solid var(--k-surface-hover)}
.ko-kv>div:nth-child(4n){border-right:0}
.ko-kv .lbl{display:block;font-size:11px;color:var(--k-dim);margin-bottom:4px}
.ko-kv b{font-weight:500;font-size:13px}
.ko-copy{margin:0 0 10px;font-size:13px;line-height:1.55;color:var(--k-text)}
.ko-sec{margin:20px 0 8px;font-size:14px;font-weight:400;color:var(--k-text)}
.ko-split{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:0 0 8px}
.ko-table-kv td{padding:8px 12px}
.ko-table-kv tbody tr,.ko-book tbody tr{cursor:default}
.ko-table-kv tbody tr:hover,.ko-book tbody tr:hover{background:transparent}
.ko-month-nav{display:flex;align-items:center;gap:16px;margin:0 0 12px;font-size:13px}
.ko-cal{display:grid;grid-template-columns:repeat(7,1fr);border-top:1px solid var(--k-border);border-left:1px solid var(--k-border);margin:0 0 12px}
.ko-cal-hd{font-size:11px;color:var(--k-dim);padding:8px 8px 6px;border-right:1px solid var(--k-border);border-bottom:1px solid var(--k-border)}
.ko-cal-cell{min-height:52px;padding:6px 8px;border-right:1px solid var(--k-border);border-bottom:1px solid var(--k-border);background:var(--k-bg);text-align:left;display:flex;flex-direction:column;justify-content:space-between;gap:8px;color:var(--k-text);font-family:inherit;cursor:pointer}
.ko-cal-cell .n{font-size:13px}
.ko-cal-cell .bar{display:block;height:3px;width:100%;background:var(--k-border)}
.ko-cal-cell[data-gap=up] .bar{background:var(--ko-ce)}
.ko-cal-cell[data-gap=down] .bar{background:var(--ko-pe)}
.ko-cal-cell[data-gap=flat] .bar{background:var(--k-amber)}
.ko-cal-cell[data-gap=closed] .bar{background:var(--k-surface-hover)}
.ko-cal-cell[data-on=true]{box-shadow:inset 0 -2px 0 var(--k-orange)}
.ko-cal-cell:disabled,.ko-cal-empty{opacity:.4;cursor:default}
.ko-cal-empty{min-height:52px;border-right:1px solid var(--k-border);border-bottom:1px solid var(--k-border)}
.ko-now{border:1px solid var(--k-border);margin:0 0 16px;padding:12px 16px 14px;background:var(--k-bg)}
.ko-now-top{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:6px}
.ko-now-phase{font-size:11px;color:var(--k-dim);font-weight:500}
.ko-now-phase[data-live="true"]{color:#f57c00}
.ko-now-clock{font-size:12px;color:var(--k-dim);font-variant-numeric:tabular-nums}
.ko-now-play{font-size:20px;font-weight:400;letter-spacing:-.2px;line-height:1.2;margin:0 0 6px}
.ko-now-sub{font-size:13px;color:var(--k-dim);margin-left:10px;letter-spacing:0;font-weight:400}
.ko-now-copy{margin:0 0 6px;font-size:13px;line-height:1.45;color:var(--k-text)}
.ko-now-meta{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12px;color:var(--k-dim);margin-top:8px}
.ko-now-bar{height:3px;background:var(--k-surface-hover);margin-top:10px}
.ko-now-bar>span{display:block;height:3px;background:var(--k-orange)}
.ko-now-actions{display:flex;flex-wrap:wrap;gap:12px 16px;align-items:center;margin-top:10px;font-size:13px}
.ko-play{margin:0 0 16px;padding:0 0 14px;border-bottom:1px solid var(--k-surface-hover)}
.ko-play-head{margin:0 0 8px;font-size:13px;color:var(--k-text);line-height:1.45}
.ko-play-meta{display:flex;flex-wrap:wrap;gap:8px 24px;font-size:13px;color:var(--k-text)}
.ko-play-meta .lbl{color:var(--k-dim);margin-right:7px;font-size:12px}
.ko-play-meta b{font-weight:500}
.ko-play-roles{display:flex;flex-direction:column;gap:10px;margin-top:10px}
@media(min-width:801px){.ko-play-roles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px 24px}}
.ko-play-roles button,.ko-play-roles>div{border:0;background:none;text-align:left;padding:0;font-size:13px;color:var(--k-text);font-family:inherit;cursor:pointer}
.ko-play-roles button:disabled{cursor:default;opacity:1}
.ko-play-roles .lbl{display:block;font-size:11px;color:var(--k-dim);margin-bottom:3px}
.ko-play-roles .ko-pill{margin-right:6px}
@media(max-width:800px){
  .ko-head,.ko-body{padding-left:16px;padding-right:16px}
  .ko-title-row{flex-wrap:wrap;margin-bottom:4px;gap:8px}
  .ko-title-row h2{width:auto;font-size:20px}
  .ko-date-value{min-width:96px;font-size:13px}
  .ko-tabs-row{flex-wrap:wrap;align-items:flex-start;gap:0}
  .ko-tabs{gap:20px;width:100%}
  .ko-ins{width:100%;gap:14px;padding-top:4px;padding-bottom:10px}
  .ko-kv{grid-template-columns:1fr 1fr}
  .ko-kv>div:nth-child(4n){border-right:1px solid var(--k-surface-hover)}
  .ko-kv>div:nth-child(2n){border-right:0}
  .ko-split{grid-template-columns:1fr}
  .ko-cal-cell{min-height:44px;padding:4px 4px 6px}
}
`;

export function AstroPane() {
  const [iso, setIso] = useState(sessionIso);
  const [underlying, setUnderlying] = useState<Underlying>('NIFTY');
  const [tab, setTab] = useState<Tab>('timings');
  const [now, setNow] = useState<Date | null>(null);
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [notes, setNotes] = useState(false);
  const [status, setStatus] = useState<LiveNow | null>(null);
  const [board, setBoard] = useState<IndexPlay[]>([]);
  const [monthCursor, setMonthCursor] = useState(() => {
    const p = getIstParts(new Date());
    return { year: p.year, month: p.month };
  });

  const nowKey = now
    ? `${formatIstIsoDate(now)}-${getIstParts(now).hour}-${getIstParts(now).minute}-${underlying}`
    : '';

  useEffect(() => {
    setNow(new Date());
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const t = new Date();
    setStatus(liveNow(t, underlying));
    setBoard(liveBoard(t));
  }, [nowKey, underlying]);

  const candles = useCandles(underlying, '5m', 400);
  const dayDate = useMemo(() => isoToDate(iso), [iso]);
  const book = useMemo(() => forecastDay(dayDate, underlying, now ?? dayDate), [dayDate, underlying, now]);
  const month = useMemo(
    () => forecastMonth(monthCursor.year, monthCursor.month, underlying, now ?? dayDate),
    [monthCursor, underlying, now, dayDate],
  );

  const clockRows = tab === 'thirty' ? book.slots : book.netResults;
  const live = book.slots.find((s) => s.isLive) ?? null;
  const nowParts = now ? getIstParts(now) : null;
  const nowMin = nowParts ? minutesOfDay(nowParts.hour, nowParts.minute) : null;
  const sameDay = Boolean(now && nowParts && formatIstIsoDate(now) === iso);
  const tape = useMemo(
    () => (candles.data?.length ? barsFromOhlcv(candles.data, iso, underlying) : null),
    [candles.data, iso, underlying],
  );
  const tapeLoading = candles.isLoading && !tape;
  const grades = useMemo(() => {
    const map = new Map<string, SlotGrade>();
    for (const s of clockRows) map.set(`${s.from}-${s.to}`, gradeSlot(s, tape, nowMin, sameDay));
    return map;
  }, [clockRows, tape, nowMin, sameDay]);
  const tally = useMemo(
    () => summariseTape(clockRows, tape, nowMin, sameDay, book.gap.kind),
    [clockRows, tape, nowMin, sameDay, book.gap.kind],
  );
  const instrument = underlyingLabel(underlying);
  const stripSlots = tab === 'thirty' ? book.slots : book.netResults;
  const liveGrade = useMemo(() => {
    if (!status?.window || !now || iso !== status.sessionIso) return undefined;
    return gradeSlot(status.window, tape, nowMin, sameDay);
  }, [status, now, iso, tape, nowMin, sameDay]);
  const liveKey =
    status?.window && iso === status.sessionIso && tab !== 'month'
      ? `${status.window.from}-${status.window.to}`
      : null;
  const chipPlay = (id: Underlying) => board.find((row) => row.id === id);

  useEffect(() => {
    if (!liveKey) return;
    setOpenKey(liveKey);
  }, [liveKey]);

  useEffect(() => {
    if (!liveKey || tab === 'month') return;
    document.getElementById('ko-live-row')?.scrollIntoView({ block: 'nearest' });
  }, [liveKey, tab]);

  const applyIso = (next: string) => {
    const snapped = nearestOpenIso(next);
    setIso(snapped);
    const [y, m] = snapped.split('-').map(Number);
    setMonthCursor({ year: y, month: m });
  };

  const goToday = () => {
    applyIso(sessionIso());
    if (tab === 'month') setTab('timings');
  };

  const shiftDay = (dir: 1 | -1) => {
    applyIso(shiftSessionIso(iso, dir));
    if (tab === 'month') setTab('timings');
  };

  const shiftMonth = (delta: number) => {
    setMonthCursor((c) => {
      let month = c.month + delta;
      let year = c.year;
      if (month < 1) { month = 12; year -= 1; }
      if (month > 12) { month = 1; year += 1; }
      return { year, month };
    });
  };

  const pickSlot = (slot: WindowSlot) => {
    if (tab === 'month') setTab('timings');
    setOpenKey(`${slot.from}-${slot.to}`);
  };

  const pickDay = (date: string) => {
    applyIso(date);
    setTab('timings');
  };

  return (
    <div className="kite-astro">
      <style>{CSS}</style>
      <div className="ko-head">
        <div className="ko-title-row">
          <h2>Astrology</h2>
          <div className="ko-date" role="group" aria-label="Session date">
            <button type="button" className="ko-date-btn" aria-label="Previous session" onClick={() => shiftDay(-1)}>‹</button>
            <label className="ko-date-value">
              {fmtNavDay(iso)}
              <input
                aria-label="Session date"
                type="date"
                value={iso}
                onChange={(e) => {
                  if (!e.target.value) return;
                  applyIso(e.target.value);
                  if (tab === 'month') setTab('timings');
                }}
              />
            </label>
            <button type="button" className="ko-date-btn" aria-label="Next session" onClick={() => shiftDay(1)}>›</button>
            <button
              type="button"
              className="ko-link"
              data-on={tab === 'month'}
              aria-label={month.label}
              aria-pressed={tab === 'month'}
              onClick={() => setTab((t) => (t === 'month' ? 'timings' : 'month'))}
            >
              {MONTHS[monthCursor.month - 1]}
            </button>
            <button type="button" className="ko-link" onClick={goToday}>Today</button>
          </div>
        </div>
        <div className="ko-tabs-row">
          <div className="ko-tabs" role="tablist" aria-label="View">
            <button type="button" role="tab" data-on={tab === 'timings'} aria-selected={tab === 'timings'} onClick={() => setTab('timings')}>Timings</button>
            <button type="button" role="tab" data-on={tab === 'thirty'} aria-selected={tab === 'thirty'} onClick={() => setTab('thirty')}>30 min</button>
          </div>
          <div className="ko-ins" role="tablist" aria-label="Underlying">
            {UNDER_SHORT.map((u) => {
              const play = chipPlay(u.id);
              return (
                <button key={u.id} type="button" role="tab" data-on={underlying === u.id} aria-selected={underlying === u.id} onClick={() => setUnderlying(u.id)}>
                  {u.short}
                  {play ? (
                    <span className={`ko-ins-side ${play.side === 'CE' ? 'text-ce' : play.side === 'PE' ? 'text-pe' : 'text-muted'}`}>
                      {play.side === 'WAIT' ? '—' : play.side === 'BOTH' ? 'BOTH' : play.side}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="ko-body">
        {now && status ? (
          <NowBoard
            status={status}
            now={now}
            grade={liveGrade}
            viewingIso={iso}
            board={board}
            onOpenSession={(date) => {
              applyIso(date);
              setTab('timings');
            }}
            onOpenWindow={(slot) => {
              applyIso(status.sessionIso);
              setTab('timings');
              setOpenKey(`${slot.from}-${slot.to}`);
            }}
          />
        ) : null}

        {tab !== 'month' ? <PlaybookStrip book={book} onPick={pickSlot} /> : null}

        <p className="ko-sub">
          {book.panchang.weekday} · {book.panchang.tithiName} {book.panchang.paksha} · {book.panchang.nakshatra} · {book.gap.firstHourNote}{' '}
          <button type="button" className="ko-link" onClick={() => setNotes((v) => !v)}>{notes ? 'Hide notes' : 'View notes'}</button>
        </p>
        {notes ? <PlaybookNotes book={book} /> : null}

        {tab === 'month' ? (
          <>
            <div className="ko-month-nav">
              <button type="button" className="ko-link" onClick={() => shiftMonth(-1)}>Prev</button>
              <span>{month.label}</span>
              <button type="button" className="ko-link" onClick={() => shiftMonth(1)}>Next</button>
            </div>
            <MonthHeat month={month} iso={iso} onPick={pickDay} />
            <div className="ko-scroll">
              <table className="ko-table ko-wide">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Gap</th>
                    <th>Open</th>
                    <th>Bias</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {month.days.map((day) => {
                    const closed = day.isWeekend || day.isHoliday;
                    const color = day.gap === 'up' ? 'var(--ko-ce)' : day.gap === 'down' ? 'var(--ko-pe)' : 'var(--k-amber)';
                    return (
                      <tr
                        key={day.date}
                        data-on={day.date === iso}
                        onClick={() => {
                          if (closed) return;
                          pickDay(day.date);
                        }}
                        style={{ cursor: closed ? 'default' : 'pointer', opacity: closed ? 0.45 : 1 }}
                      >
                        <td>{formatIstDate(isoToDate(day.date))}{day.isToday ? ' · today' : ''}</td>
                        <td style={{ color: closed ? 'var(--k-dim)' : color }}>
                          {closed ? (day.isHoliday ? day.holidayName || 'Holiday' : 'Weekend') : day.gapLabel}
                        </td>
                        <td>{closed ? '—' : day.openAction}</td>
                        <td>{closed ? '—' : day.bias}</td>
                        <td style={{ color: 'var(--k-dim)' }}>{day.note}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <>
            <SessionStrip slots={stripSlots} iso={iso} tape={tape} nowMin={nowMin} sameDay={sameDay} onPick={pickSlot} />
            <div className="ko-scroll">
              <table className="ko-table ko-wide">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Type</th>
                    <th>Instrument</th>
                    <th>Product</th>
                    <th>Net results</th>
                    <th>Play</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {clockRows.map((slot) => {
                    const key = `${slot.from}-${slot.to}`;
                    const grade = grades.get(key);
                    const open = openKey === key;
                    return (
                      <React.Fragment key={key}>
                        <tr data-on={open} data-live={slot.isLive} id={slot.isLive ? 'ko-live-row' : undefined} onClick={() => setOpenKey(open ? null : key)}>
                          <td>
                            {slot.from} – {slot.to}
                            {slot.isLive ? <span className="ko-tag">LIVE</span> : null}
                          </td>
                          <td><span className={sideClass(slot.side)}>{sideLabel(slot.side)}</span></td>
                          <td style={{ whiteSpace: 'nowrap' }}>{instrument}<span className="ko-tag">NSE</span></td>
                          <td><span className={productClass(slot.product)}>{slot.product}</span></td>
                          <td>
                            {slot.regime}
                            <span style={{ color: 'var(--k-dim)' }}>
                              {' '}· {slot.toMin - slot.fromMin}m · {slot.hora}
                              {slot.kalam.rahu ? ' · Rahu' : ''}
                              {slot.kalam.yamagandam ? ' · Yama' : ''}
                            </span>
                          </td>
                          <td style={{ color: actionColor(slot.action, slot.side) }}>{slot.action}</td>
                          <td>
                            {!grade || grade.kind === 'NONE' ? (
                              <span style={{ color: 'var(--k-dim)' }}>{tapeLoading ? '…' : '—'}</span>
                            ) : grade.kind === 'PENDING' ? (
                              <span style={{ color: 'var(--k-dim)' }}>Pending</span>
                            ) : (
                              <span>
                                <span className={gradeClass(grade.kind)}>{grade.label}</span>
                                {grade.delta !== null && (
                                  <span style={{ color: 'var(--k-dim)' }}> {grade.delta >= 0 ? '+' : ''}{grade.delta.toFixed(0)}</span>
                                )}
                              </span>
                            )}
                          </td>
                        </tr>
                        {open && (
                          <tr className="ko-expand">
                            <td colSpan={7}>
                              {slot.suggestion}
                              <div style={{ color: 'var(--k-dim)', marginTop: 4 }}>{slot.why}</div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="ko-foot">
              <span><span className="lbl">Gap</span><span style={{ color: gapColor(book.gap.kind) }}>{book.gap.label}</span></span>
              <span><span className="lbl">Open</span>{book.gap.openAction}</span>
              <span><span className="lbl">Window</span>{live ? live.action : 'Outside cash'}</span>
              <span>
                <span className="lbl">Tape</span>
                {tally.directional
                  ? `${tally.hits}/${tally.directional} HIT${tally.sits ? ` · ${tally.sits} sit` : ''} · ${tally.pnl >= 0 ? '+' : ''}${tally.pnl.toFixed(0)}`
                  : candles.isLoading ? 'Loading…' : '—'}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
