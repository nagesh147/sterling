import React, { useEffect, useMemo, useState } from 'react';
import { k } from '../../styles/kiteUI';
import { forecastDay, forecastMonth, liveNow } from '../../lib/astro/engine';
import { lastCompletedSessionIso } from '../../lib/astro/holidays';
import { barsFromOhlcv, gradeSlot, summariseTape, type SlotGrade } from '../../lib/astro/tape';
import { formatIstDate, formatIstIsoDate, getIstParts, minutesOfDay, utcFromIstParts } from '../../lib/astro/time';
import { UNDERLYINGS, type GapKind, type LiveNow, type TradeAction, type TradeSide, type Underlying, type WindowSlot } from '../../lib/astro/types';
import { useCandles } from '../../hooks/useCandles';
import { MonthHeat } from './astro/MonthHeat';
import { NowBoard } from './astro/NowBoard';
import { PlaybookBoard } from './astro/PlaybookBoard';
import { SessionStrip } from './astro/SessionStrip';

type Tab = 'timings' | 'thirty' | 'playbook' | 'month';

function sessionIso(): string {
  return lastCompletedSessionIso(new Date());
}

function isoToDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return utcFromIstParts(y, m, d, 9, 0, 0);
}

function gapColor(kind: GapKind): string {
  if (kind === 'up') return 'var(--k-green)';
  if (kind === 'down') return 'var(--k-red)';
  return 'var(--k-amber)';
}

function actionColor(action: TradeAction, side: TradeSide): string {
  if (action === 'AVOID' || action === 'WAIT') return 'var(--k-dim)';
  if (side === 'CE') return 'var(--k-green)';
  if (side === 'PE') return 'var(--k-red)';
  return 'var(--k-amber)';
}

function underlyingLabel(id: Underlying): string {
  return UNDERLYINGS.find((u) => u.id === id)?.label ?? id;
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
.kite-astro{display:flex;flex-direction:column;height:100%;min-height:100%;background:var(--k-bg);color:var(--k-text);font-family:${k.fontFamily};font-size:14px}
.kite-astro *{box-sizing:border-box}
.ko-head{padding:0 32px;border-bottom:1px solid var(--k-surface-hover);margin-top:12px}
.ko-title-row{display:flex;align-items:center;gap:16px;margin:0 0 24px;min-height:32px}
.ko-title-row h2{margin:0;font-size:24px;font-weight:400;color:var(--k-text);flex:1}
.ko-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.ko-tools select,.ko-tools input[type=date]{height:32px;border:1px solid var(--k-border);background:var(--k-bg);color:var(--k-text);font-size:13px;padding:0 8px;border-radius:2px;font-family:inherit}
.ko-link{border:0;background:none;color:var(--k-blue-kite);font-size:13px;padding:0;cursor:pointer;font-family:inherit}
.ko-link:hover{text-decoration:underline}
.ko-tabs{display:flex;gap:32px;margin-bottom:-1px;overflow-x:auto}
.ko-tabs button{padding:0 0 12px;border:0;background:none;color:var(--k-text);font-size:14px;font-weight:400;border-bottom:2px solid transparent;white-space:nowrap;cursor:pointer;font-family:inherit;transition:color .2s}
.ko-tabs button[data-on="true"]{color:var(--k-orange);border-bottom-color:var(--k-orange)}
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
.ko-pill-ce{color:var(--k-green);background:rgba(76,175,80,.1)}
.ko-pill-pe{color:var(--k-red);background:rgba(229,57,53,.1)}
.ko-pill-wait{color:var(--k-dim);background:rgba(155,155,155,.1)}
.ko-st{display:inline-block;padding:2px 6px;border-radius:3px;font-size:11px}
.ko-st-hit{color:var(--k-green);background:rgba(76,175,80,.1)}
.ko-st-miss{color:var(--k-red);background:rgba(223,81,76,.1)}
.ko-st-live{color:#f57c00;background:rgba(255,152,0,.1)}
.ko-st-sit{color:var(--k-dim);background:rgba(155,155,155,.1)}
.ko-tag{display:inline-block;margin-left:8px;font-size:9px;color:var(--k-dim);background:var(--k-surface-hover);padding:1px 4px;border-radius:2px;vertical-align:middle}
.ko-prod{display:inline-block;padding:2px 7px;border-radius:2px;font-size:10px;font-weight:500}
.ko-prod-mis{color:var(--k-blue-kite);background:rgba(56,126,209,.1)}
.ko-prod-nrml{color:#c856a2;background:rgba(200,86,162,.1)}
.ko-prod-other{color:var(--k-dim);background:var(--k-surface-hover)}
.ko-foot{display:flex;justify-content:flex-end;flex-wrap:wrap;gap:24px;padding:13px 16px;border-top:1px solid var(--k-border);font-size:12px}
.ko-foot .lbl{color:var(--k-dim);margin-right:7px}
.text-up{color:var(--k-green)}.text-down{color:var(--k-red)}.text-warn{color:var(--k-amber)}.text-ce{color:var(--k-green)}.text-pe{color:var(--k-red)}.text-muted{color:var(--k-dim)}.text-faint{color:var(--k-dim)}.text-ink{color:var(--k-text)}
.ko-strip{margin:0 0 18px}
.ko-strip svg{width:100%;height:auto;display:block}
.ko-strip g{cursor:pointer}
.ko-strip-tapebg{fill:var(--k-surface-2)}
.ko-strip-ce{fill:var(--k-green)}.ko-strip-pe{fill:var(--k-red)}.ko-strip-both{fill:var(--k-amber)}.ko-strip-wait{fill:#d6d6d6}.ko-strip-avoid{fill:#bdbdbd}
.ko-strip-tick{stroke:var(--k-border);stroke-width:1}
.ko-strip-now{stroke:var(--k-orange);stroke-width:1.2}
.ko-strip-lbl,.ko-strip-hora,.ko-strip-empty{fill:var(--k-dim);font-size:10px;font-family:inherit}
.ko-strip-hora{font-size:9px}
.ko-strip-leg{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:var(--k-dim);margin-top:8px;align-items:center}
.ko-strip-leg i{display:inline-block;width:8px;height:8px;margin-right:5px;border-radius:1px}
.ko-swatch-ce{background:var(--k-green)}.ko-swatch-pe{background:var(--k-red)}.ko-swatch-both{background:var(--k-amber)}.ko-swatch-wait{background:#d6d6d6}
.ko-mix{display:flex;height:4px;margin-top:8px;background:var(--k-surface-hover)}
.ko-mix-ce{background:var(--k-green)}.ko-mix-pe{background:var(--k-red)}.ko-mix-both{background:var(--k-amber)}.ko-mix-wait{background:#d6d6d6}
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
.ko-cal-cell[data-gap=up] .bar{background:var(--k-green)}
.ko-cal-cell[data-gap=down] .bar{background:var(--k-red)}
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
@media(max-width:800px){
  .ko-head,.ko-body{padding-left:16px;padding-right:16px}
  .ko-title-row{flex-wrap:wrap;margin-bottom:16px}
  .ko-title-row h2{width:100%}
  .ko-tabs{gap:20px}
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
    setStatus(liveNow(new Date(), underlying));
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

  const goToday = () => {
    const t = sessionIso();
    setIso(t);
    const [y, m] = t.split('-').map(Number);
    setMonthCursor({ year: y, month: m });
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
    if (tab === 'playbook') setTab('timings');
    setOpenKey(`${slot.from}-${slot.to}`);
  };

  return (
    <div className="kite-astro">
      <style>{CSS}</style>
      <div className="ko-head">
        <div className="ko-title-row">
          <h2>Astrology</h2>
          <div className="ko-tools">
            <select aria-label="Underlying" value={underlying} onChange={(e) => setUnderlying(e.target.value as Underlying)}>
              {UNDERLYINGS.map((u) => (
                <option key={u.id} value={u.id}>{u.label}</option>
              ))}
            </select>
            <input
              aria-label="Session date"
              type="date"
              value={iso}
              onChange={(e) => {
                if (!e.target.value) return;
                setIso(e.target.value);
                const [y, m] = e.target.value.split('-').map(Number);
                setMonthCursor({ year: y, month: m });
              }}
            />
            <button type="button" className="ko-link" onClick={goToday}>Today</button>
          </div>
        </div>
        <div className="ko-tabs">
          <button type="button" data-on={tab === 'timings'} onClick={() => setTab('timings')}>Timings</button>
          <button type="button" data-on={tab === 'thirty'} onClick={() => setTab('thirty')}>30 min</button>
          <button type="button" data-on={tab === 'playbook'} onClick={() => setTab('playbook')}>Playbook</button>
          <button type="button" data-on={tab === 'month'} onClick={() => setTab('month')}>{month.label}</button>
        </div>
      </div>

      <div className="ko-body">
        {now && status ? (
          <NowBoard
            status={status}
            now={now}
            grade={liveGrade}
            viewingIso={iso}
            onOpenSession={(date) => {
              setIso(date);
              setTab('playbook');
              const [y, m] = date.split('-').map(Number);
              setMonthCursor({ year: y, month: m });
            }}
            onOpenWindow={(slot) => {
              setIso(status.sessionIso);
              const [y, m] = status.sessionIso.split('-').map(Number);
              setMonthCursor({ year: y, month: m });
              setTab('timings');
              setOpenKey(`${slot.from}-${slot.to}`);
            }}
          />
        ) : null}
        <p className="ko-sub">
          {book.panchang.weekday} · {book.panchang.tithiName} {book.panchang.paksha} · {book.panchang.nakshatra} · {book.gap.firstHourNote}{' '}
          <button type="button" className="ko-link" onClick={() => setNotes((v) => !v)}>{notes ? 'Hide notes' : 'View notes'}</button>
        </p>
        {notes && (
          <ul className="ko-notes">
            {book.gap.reasons.map((r) => <li key={r}>{r}</li>)}
          </ul>
        )}

        {tab === 'month' ? (
          <>
            <div className="ko-month-nav">
              <button type="button" className="ko-link" onClick={() => shiftMonth(-1)}>Prev</button>
              <span>{month.label}</span>
              <button type="button" className="ko-link" onClick={() => shiftMonth(1)}>Next</button>
            </div>
            <MonthHeat month={month} iso={iso} onPick={(date) => { setIso(date); setTab('playbook'); }} />
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
                    const color = day.gap === 'up' ? 'var(--k-green)' : day.gap === 'down' ? 'var(--k-red)' : 'var(--k-amber)';
                    return (
                      <tr
                        key={day.date}
                        data-on={day.date === iso}
                        onClick={() => {
                          if (closed) return;
                          setIso(day.date);
                          setTab('playbook');
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
        ) : tab === 'playbook' ? (
          <>
            <SessionStrip slots={book.netResults} iso={iso} tape={tape} nowMin={nowMin} sameDay={sameDay} onPick={pickSlot} />
            <PlaybookBoard book={book} />
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
                        <tr data-on={open} onClick={() => setOpenKey(open ? null : key)}>
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
              <span><span className="lbl">CE / PE</span>{book.playbook.bestCe?.from ?? '—'} / {book.playbook.bestPe?.from ?? '—'}</span>
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
