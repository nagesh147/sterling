import React, { useEffect, useMemo, useState } from "react";
import { forecastDay, forecastMonth, liveBoard, liveNow } from '../../lib/astro/engine';
import { useCandles } from '../../hooks/useCandles';
import { lastCompletedSessionIso, nearestOpenIso, shiftSessionIso } from '../../lib/astro/holidays';
import { barsFromOhlcv, gradeSlot, summariseTape, type SlotGrade } from '../../lib/astro/tape';
import { formatIstIsoDate, getIstParts, minutesOfDay, utcFromIstParts } from '../../lib/astro/time';
import { WEEKDAYS, type IndexPlay, type LiveNow, type Underlying, type WindowSlot } from '../../lib/astro/types';
import { k } from '../../styles/kiteUI';
import { actionTone } from './astro/palette';
import { MonthHeat } from './astro/MonthHeat';
import { NowBoard } from './astro/NowBoard';
import { PlaybookNotes, PlaybookStrip } from './astro/PlaybookBoard';
import { SessionStrip } from './astro/SessionStrip';

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
.ko-ins-side{margin-left:5px;font-size:12px;font-weight:500}
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
.ko-strip-ce{fill:var(--ko-ce)}.ko-strip-pe{fill:var(--ko-pe)}.ko-strip-both{fill:#bdbdbd}.ko-strip-wait{fill:#d6d6d6}.ko-strip-avoid{fill:#bdbdbd}
.ko-strip-upline{stroke:var(--ko-ce);fill:none}.ko-strip-downline{stroke:var(--ko-pe);fill:none}
.ko-strip-tick{stroke:var(--k-border);stroke-width:1}
.ko-strip-now{stroke:var(--k-orange);stroke-width:1.2}
.ko-strip-lbl,.ko-strip-hora,.ko-strip-empty{fill:var(--k-dim);font-size:10px;font-family:inherit}
.ko-strip-hora{font-size:9px}
.ko-strip-leg{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:var(--k-dim);margin-top:8px;align-items:center}
.ko-strip-leg i{display:inline-block;width:8px;height:8px;margin-right:5px;border-radius:1px}
.ko-swatch-ce{background:var(--ko-ce)}.ko-swatch-pe{background:var(--ko-pe)}.ko-swatch-both{background:#bdbdbd}.ko-swatch-wait{background:#d6d6d6}
.ko-mix{display:flex;height:4px;margin-top:8px;background:var(--k-surface-hover)}
.ko-mix-ce{background:var(--ko-ce)}.ko-mix-pe{background:var(--ko-pe)}.ko-mix-both{background:#bdbdbd}.ko-mix-wait{background:#d6d6d6}
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
.ko-cal-cell[data-gap=flat] .bar{background:#d6d6d6}
.ko-cal-cell[data-gap=closed] .bar{background:var(--k-surface-hover)}
.ko-cal-cell[data-on=true]{box-shadow:inset 0 -2px 0 var(--k-orange)}
.ko-cal-cell:disabled,.ko-cal-empty{opacity:.4;cursor:default}
.ko-cal-empty{min-height:52px;border-right:1px solid var(--k-border);border-bottom:1px solid var(--k-border)}
.ko-now{border:1px solid var(--k-border);margin:0 0 12px;padding:10px 16px 12px;background:var(--k-bg)}
.ko-now-top{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:4px}
.ko-now-phase{font-size:11px;color:var(--k-dim);font-weight:500;letter-spacing:.04em}
.ko-now-phase[data-live="true"]{color:#f57c00}
.ko-now-clock{font-size:13px;color:var(--k-dim);font-variant-numeric:tabular-nums}
.ko-now-play{display:block;font-size:20px;font-weight:400;letter-spacing:-.2px;line-height:1.2;margin:0 0 4px}
.ko-now-sub{font-size:13px;color:var(--k-dim);margin-left:0;letter-spacing:0;font-weight:400}
.ko-now-copy{margin:0 0 4px;font-size:13px;line-height:1.45;color:var(--k-text)}
.ko-now-meta{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--k-dim);margin-top:6px}
.ko-now-bar{height:2px;background:var(--k-surface-hover);margin-top:8px}
.ko-now-bar>span{display:block;height:2px;background:var(--k-orange)}
.ko-now-actions{display:flex;flex-wrap:wrap;gap:12px 16px;align-items:center;margin-top:8px;font-size:13px}
.ko-play{margin:0 0 12px;padding:0 0 12px;border-bottom:1px solid var(--k-surface-hover)}
.ko-play-head{margin:0 0 8px;font-size:13px;color:var(--k-text);line-height:1.45}
.ko-play-meta{display:flex;flex-wrap:wrap;gap:8px 24px;font-size:13px;color:var(--k-text)}
.ko-play-meta .lbl{color:var(--k-dim);margin-right:7px;font-size:12px}
.ko-play-meta b{font-weight:500}
.ko-play-roles{display:flex;flex-direction:column;gap:10px;margin-top:0}
@media(min-width:801px){.ko-play-roles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px 24px}}
.ko-play-roles button,.ko-play-roles>div{border:0;background:none;text-align:left;padding:0;font-size:13px;color:var(--k-text);font-family:inherit;cursor:pointer}
.ko-play-roles button:disabled{cursor:default;opacity:1}
.ko-play-roles button[data-state="done"]{opacity:.45}
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

.kite-astro .ko{display:flex;flex-direction:column;height:100%;min-height:100%}
.ko-desk{display:grid;grid-template-columns:minmax(0,1fr) 272px;gap:28px;align-items:start}
.ko-rail{position:sticky;top:8px;min-width:0}
.ko-rail-head{display:flex;align-items:center;gap:10px;margin:0 0 10px;font-size:13px;color:var(--k-text)}
.ko-rail-head span{flex:1;text-align:center;font-weight:500}
.ko-tally{margin-left:14px;font-size:12px;color:var(--k-dim)}
.ko-sub{display:flex;flex-wrap:wrap;align-items:center}
.ko-clock{min-width:0}
.ko-clock td,.ko-clock th{padding:10px 12px}
.ko-time{white-space:nowrap}
.ko-time-meta{display:block;color:var(--k-dim);font-size:11px;margin-top:2px}
.ko-play-roles button[data-state="now"]{box-shadow:inset 2px 0 var(--k-orange);padding-left:10px}
.ko-cal-top{display:flex;justify-content:space-between;align-items:baseline;gap:4px}
.ko-cal-act{font-size:10px;font-weight:500}
.ko-cal-cell[data-today="true"] .n{color:var(--k-orange);font-weight:500}
.ko-cal-leg{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0 4px;font-size:11px;color:var(--k-dim)}
.ko-cal-leg i{display:inline-block;width:8px;height:8px;margin-right:5px;border-radius:1px}
.ko-cal-sum{margin:0 0 4px;font-size:11px;color:var(--k-dim);line-height:1.4}
.ko-strip-upfill{fill:color-mix(in srgb,var(--ko-ce) 14%,transparent)}
.ko-strip-downfill{fill:color-mix(in srgb,var(--ko-pe) 14%,transparent)}
.ko-strip-side{fill:#fff;font-size:9px;font-family:inherit;font-weight:500;pointer-events:none}
.ko-strip-hit{fill:var(--ko-ce)}.ko-strip-miss{fill:var(--ko-pe)}.ko-strip-live{fill:var(--k-orange)}
.ko-rail .ko-cal-cell{min-height:42px;padding:5px 6px}
.ko-desk[data-tab="month"]{grid-template-columns:minmax(0,640px)}
.ko-desk[data-tab="month"] .ko-main{display:none}
@media(max-width:1099px){
  .ko-desk{display:block}
  .ko-rail{display:none;position:static}
  .ko-desk[data-tab="month"] .ko-main{display:none}
  .ko-desk[data-tab="month"] .ko-rail{display:block}
}
.ko-ins-side {
  margin-left: 5px;
  font-size: 12px;
  font-weight: 500;
}
.ko-title-row h2 {
  font-size: 20px;
}
.ko-now-phase[data-live="true"] {
  color: var(--k-orange);
}
.ko-now-play {
  display: block;
  font-size: 20px;
  font-weight: 400;
  letter-spacing: -0.2px;
  line-height: 1.2;
  margin: 0 0 4px;
}
.ko-now-clock {
  font-size: 13px;
}
.ko-st-live {
  color: var(--k-orange);
  background: color-mix(in srgb, var(--k-orange) 10%, transparent);
}
.ko-plan {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 8px;
  text-align: left;
  min-height: 36px;
  padding: 6px 10px;
  border: 1px solid var(--k-border);
  background: var(--k-bg);
  font: inherit;
  font-size: 13px;
  color: var(--k-text);
  cursor: pointer;
}
.ko-plan[data-state="now"] {
  box-shadow: inset 2px 0 var(--k-orange);
}
.ko-plan[data-state="done"] {
  opacity: 0.55;
}
.ko-plan-kicker {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--k-dim);
}
.ko-plan-play {
  font-weight: 500;
}
.ko-now-next {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--k-dim);
  line-height: 1.4;
}
.ko-now-copy {
  text-wrap: pretty;
}
.ko-strip-both,
.ko-swatch-both,
.ko-mix-both {
  background: #bdbdbd;
  fill: #bdbdbd;
}
.ko-cal-cell[data-gap="flat"] .bar {
  background: #d6d6d6;
}
.ko-tag-now {
  color: var(--k-orange);
  background: var(--k-orange)1a;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  margin-left: 0;
}

.ko-alerts {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  gap: 8px;
  margin: 0 0 12px;
}
.ko-alert {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  text-align: left;
  min-height: 44px;
  padding: 8px 12px;
  border: 1px solid var(--k-border);
  background: var(--k-bg);
  font: inherit;
  color: var(--k-text);
}
.ko-alert[data-kind="now"] {
  box-shadow: inset 2px 0 var(--k-orange);
}
.ko-alert-kicker {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--k-dim);
}
.ko-alert-body {
  font-size: 13px;
  line-height: 1.4;
}
.ko-alert-body b {
  font-weight: 500;
}
.ko-alert-enable {
  align-self: center;
  min-height: 44px;
  padding: 0 4px;
}

.ko-acc {
  border-top: 1px solid var(--k-surface-hover);
  margin: 0 0 8px;
}
.ko-acc-sum,
.ko-acc-head {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 44px;
  padding: 8px 4px 8px 10px;
  border: 0;
  border-bottom: 1px solid var(--k-surface-hover);
  background: transparent;
  text-align: left;
  font: inherit;
  font-size: 13px;
  color: var(--k-text);
}
.ko-acc-sum {
  color: var(--k-dim);
  font-size: 13px;
}
.ko-acc-item[data-live="true"] .ko-acc-head {
  box-shadow: inset 2px 0 var(--k-orange);
  background: color-mix(in srgb, var(--k-orange) 6%, var(--k-bg));
}
.ko-acc-item[data-on="true"] .ko-acc-head {
  background: var(--k-surface-2);
}
.ko-acc-item[data-live="true"][data-on="true"] .ko-acc-head {
  background: color-mix(in srgb, var(--k-orange) 6%, var(--k-bg));
}
.ko-acc-time {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  min-width: 6.6rem;
}
.ko-acc-play {
  flex: 1;
  min-width: 0;
  font-weight: 500;
}
.ko-acc-result {
  flex-shrink: 0;
  font-size: 13px;
}
.ko-acc-chev {
  margin-left: auto;
  flex-shrink: 0;
  color: var(--k-dim);
  font-size: 11px;
  width: 1em;
  text-align: center;
}
.ko-acc-body {
  padding: 8px 12px 14px 12px;
  border-bottom: 1px solid var(--k-surface-hover);
  background: var(--k-surface-2);
  font-size: 13px;
  line-height: 1.5;
  color: var(--k-text);
  text-wrap: pretty;
}
.ko-acc-body p {
  margin: 0 0 6px;
}
.ko-acc-body p:last-child {
  margin-bottom: 0;
}
.ko-acc-meta {
  color: var(--k-dim);
  font-size: 11px;
}
.ko-acc-item[data-live="true"] .ko-acc-body {
  background: color-mix(in srgb, var(--k-orange) 6%, var(--k-bg));
}

@media (width <= 1099px) {
  .ko-desk {
    display: block;
  }
  .ko-rail {
    display: none;
    position: static;
  }
  .ko-desk[data-tab="month"] .ko-main {
    display: none;
  }
  .ko-desk[data-tab="month"] .ko-rail {
    display: block;
  }
}
@media (width <= 800px) {
  .ko-acc-time {
    min-width: 0;
  }
  .ko-acc-head {
    flex-wrap: wrap;
    row-gap: 4px;
  }
  .ko-acc-play {
    flex-basis: 100%;
    order: 5;
  }
  .ko-acc-chev {
    order: 6;
  }
}@media (width<=800px){.ko-head,.ko-body{padding-left:16px;padding-right:16px}.ko-title-row{flex-wrap:wrap;gap:8px;margin-bottom:4px}.ko-title-row h2{width:auto;font-size:20px}.ko-date-value{min-width:96px;font-size:13px}.ko-tabs-row{flex-wrap:wrap;align-items:flex-start;gap:0}.ko-tabs{gap:20px;width:100%}.ko-ins{gap:14px;width:100%;padding-top:4px;padding-bottom:10px}.kd-shell{padding:20px 16px}.kd-margins{grid-template-columns:1fr}.kd-margin-card+.kd-margin-card{border-top:1px solid var(--k-border);border-left:0;margin-top:24px;padding:24px 0 0}.kd-margin-card{padding:0}.kd-margin-body{flex-direction:column}.kd-margin-meta{width:100%;min-width:0}.ko-kv{grid-template-columns:1fr 1fr}.ko-kv>div:nth-child(4n){border-right:1px solid var(--k-surface-hover)}.ko-kv>div:nth-child(2n){border-right:0}.ko-split{grid-template-columns:1fr}.ko-cal-cell{min-height:44px;padding:4px 4px 6px}}
`;


type Tab = "session" | "thirty" | "month";

function sessionIso(): string {
  return lastCompletedSessionIso(new Date());
}

function isoToDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return utcFromIstParts(y, m, d, 9, 0, 0);
}

const UNDER_SHORT: { id: Underlying; short: string }[] = [
  { id: "NIFTY", short: "Nifty" },
  { id: "BANKNIFTY", short: "Bank" },
  { id: "FINNIFTY", short: "Fin" },
  { id: "SENSEX", short: "Sensex" },
  { id: "MIDCPNIFTY", short: "Midcap" },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function fmtNavDay(iso: string): string {
  const p = getIstParts(isoToDate(iso));
  return `${WEEKDAYS[p.weekday].slice(0, 3)}, ${p.day} ${MONTHS[p.month - 1]}`;
}

function slotKey(slot: WindowSlot): string {
  return `${slot.from}-${slot.to}`;
}

function sideClass(side: WindowSlot["side"]): string {
  if (side === "CE") return "ko-pill ko-pill-ce";
  if (side === "PE") return "ko-pill ko-pill-pe";
  return "ko-pill ko-pill-wait";
}

function sideLabel(side: WindowSlot["side"]): string {
  if (side === "CE") return "CE";
  if (side === "PE") return "PE";
  if (side === "BOTH") return "BOTH";
  return "WAIT";
}

function gradeClass(kind: SlotGrade["kind"]): string {
  if (kind === "HIT") return "ko-st ko-st-hit";
  if (kind === "MISS") return "ko-st ko-st-miss";
  if (kind === "LIVE") return "ko-st ko-st-live";
  if (kind === "SIT") return "ko-st ko-st-sit";
  return "ko-st ko-st-sit";
}

function stampLive(
  slots: WindowSlot[],
  nowMin: number | null,
  mode: "live" | "past" | "future",
): WindowSlot[] {
  if (mode === "live" && nowMin != null) {
    return slots.map((s) => ({
      ...s,
      isLive: nowMin >= s.fromMin && nowMin < s.toMin,
      isPast: nowMin >= s.toMin,
    }));
  }
  const past = mode === "past";
  return slots.map((s) => ({ ...s, isLive: false, isPast: past }));
}

function GradeMark({ grade, loading }: { grade: SlotGrade | undefined; loading: boolean }) {
  if (loading && (!grade || grade.kind === "NONE")) {
    return <span className="text-muted">…</span>;
  }
  if (!grade || grade.kind === "NONE") {
    return <span className="text-muted">—</span>;
  }
  if (grade.kind === "PENDING") {
    return <span className="text-muted">—</span>;
  }
  return (
    <span>
      <span className={gradeClass(grade.kind)}>{grade.label}</span>
      {grade.delta !== null && (
        <span className="text-muted">
          {" "}
          {grade.delta >= 0 ? "+" : ""}
          {grade.delta.toFixed(0)}
        </span>
      )}
    </span>
  );
}

export function AstroPane() {
  const [iso, setIso] = useState(sessionIso);
  const [underlying, setUnderlying] = useState<Underlying>("NIFTY");
  const [tab, setTab] = useState<Tab>("session");
  const [now, setNow] = useState<Date | null>(null);
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [earlierOpen, setEarlierOpen] = useState(false);
  const [laterOpen, setLaterOpen] = useState(false);
  const [notes, setNotes] = useState(false);
  const candles = useCandles(underlying, '5m', 400);
  const [status, setStatus] = useState<LiveNow | null>(null);
  const [board, setBoard] = useState<IndexPlay[]>([]);
  const [monthCursor, setMonthCursor] = useState(() => {
    const p = getIstParts(new Date());
    return { year: p.year, month: p.month };
  });

  const nowParts = now ? getIstParts(now) : null;
  const minuteKey = nowParts ? `${nowParts.year}-${nowParts.month}-${nowParts.day}-${nowParts.hour}-${nowParts.minute}-${underlying}` : "";
  const todayIso = now ? formatIstIsoDate(now) : "";

  useEffect(() => {
    setNow(new Date());
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (!minuteKey) return;
    const t = new Date();
    setStatus(liveNow(t, underlying));
    setBoard(liveBoard(t));
  }, [minuteKey, underlying]);

  const dayDate = useMemo(() => isoToDate(iso), [iso]);
  const tape = useMemo(
    () => (candles.data?.length ? barsFromOhlcv(candles.data, iso, underlying) : null),
    [candles.data, iso, underlying],
  );
  const tapeLoading = candles.isLoading && !tape;
  const tapeError = tape && tape.bars.length ? null : candles.isLoading ? null : "No tape";
  const book = useMemo(() => forecastDay(dayDate, underlying, dayDate), [dayDate, underlying]);
  const month = useMemo(() => {
    const stamp = todayIso || formatIstIsoDate(dayDate);
    const [y, m, d] = stamp.split("-").map(Number);
    return forecastMonth(monthCursor.year, monthCursor.month, underlying, utcFromIstParts(y, m, d, 9, 0, 0));
  }, [monthCursor.year, monthCursor.month, underlying, todayIso, dayDate]);

  const nowMin = nowParts ? minutesOfDay(nowParts.hour, nowParts.minute) : null;
  const sameDay = Boolean(now && todayIso === iso);
  const viewMode: "live" | "past" | "future" = !todayIso ? "future" : iso === todayIso ? "live" : iso < todayIso ? "past" : "future";
  const rawRows = tab === "thirty" ? book.slots : book.netResults;
  const clockRows = useMemo(() => stampLive(rawRows, nowMin, viewMode), [rawRows, nowMin, viewMode]);
  const grades = useMemo(() => {
    const map = new Map<string, SlotGrade>();
    for (const s of clockRows) map.set(slotKey(s), gradeSlot(s, tape, nowMin, sameDay));
    return map;
  }, [clockRows, tape, nowMin, sameDay]);
  const tally = useMemo(
    () => summariseTape(clockRows, tape, nowMin, sameDay, book.gap.kind),
    [clockRows, tape, nowMin, sameDay, book.gap.kind],
  );
  const liveGrade = useMemo(() => {
    if (!status?.window || !now || iso !== status.sessionIso) return undefined;
    return gradeSlot(status.window, tape, nowMin, sameDay);
  }, [status, now, iso, tape, nowMin, sameDay]);
  const chipPlay = (id: Underlying) => board.find((row) => row.id === id);

  const liveKey = useMemo(() => {
    const live = clockRows.find((s) => s.isLive);
    return live ? slotKey(live) : "";
  }, [clockRows]);

  useEffect(() => {
    if (!liveKey) return;
    setOpenKey(liveKey);
    setEarlierOpen(false);
    setLaterOpen(false);
  }, [liveKey]);

  const applyIso = (next: string) => {
    const snapped = nearestOpenIso(next);
    setIso(snapped);
    const [y, m] = snapped.split("-").map(Number);
    setMonthCursor({ year: y, month: m });
  };

  const goToday = () => applyIso(sessionIso());
  const shiftDay = (dir: 1 | -1) => applyIso(shiftSessionIso(iso, dir));

  const shiftMonth = (delta: number) => {
    setMonthCursor((c) => {
      let month = c.month + delta;
      let year = c.year;
      if (month < 1) {
        month = 12;
        year -= 1;
      }
      if (month > 12) {
        month = 1;
        year += 1;
      }
      return { year, month };
    });
  };

  const pickSlot = (slot: WindowSlot) => {
    if (tab === "month") setTab("session");
    const key = slotKey(slot);
    setOpenKey(key);
    const row = clockRows.find((s) => slotKey(s) === key);
    if (row?.isPast) setEarlierOpen(true);
    if (row && !row.isPast && !row.isLive) {
      const upcoming = clockRows.filter((s) => !s.isPast && !s.isLive);
      if (upcoming[0] && slotKey(upcoming[0]) !== key) setLaterOpen(true);
    }
  };

  const pickDay = (date: string) => {
    applyIso(date);
    setTab("session");
  };

  return (
    <div className="kite-astro">
      <style>{CSS}</style>
      <div className="ko">
      <div className="ko-head">
        <div className="ko-title-row">
          <h2>Astrology</h2>
          <div className="ko-date" role="group" aria-label="Session date">
            <button type="button" className="ko-date-btn" aria-label="Previous session" onClick={() => shiftDay(-1)}>
              ‹
            </button>
            <label className="ko-date-value">
              {fmtNavDay(iso)}
              <input
                aria-label="Session date"
                type="date"
                value={iso}
                onChange={(e) => {
                  if (!e.target.value) return;
                  applyIso(e.target.value);
                }}
              />
            </label>
            <button type="button" className="ko-date-btn" aria-label="Next session" onClick={() => shiftDay(1)}>
              ›
            </button>
            <button type="button" className="ko-link" onClick={goToday}>
              Today
            </button>
          </div>
        </div>
        <div className="ko-tabs-row">
          <div className="ko-tabs" role="tablist" aria-label="View">
            <button type="button" role="tab" data-on={tab === "session"} aria-selected={tab === "session"} onClick={() => setTab("session")}>
              Session
            </button>
            <button type="button" role="tab" data-on={tab === "thirty"} aria-selected={tab === "thirty"} onClick={() => setTab("thirty")}>
              30 min
            </button>
            <button type="button" role="tab" data-on={tab === "month"} aria-selected={tab === "month"} onClick={() => setTab("month")}>
              Month
            </button>
          </div>
          <div className="ko-ins" role="tablist" aria-label="Underlying">
            {UNDER_SHORT.map((u) => {
              const play = chipPlay(u.id);
              return (
                <button
                  key={u.id}
                  type="button"
                  role="tab"
                  data-on={underlying === u.id}
                  aria-selected={underlying === u.id}
                  onClick={() => setUnderlying(u.id)}
                >
                  {u.short}
                  {play && play.side !== "WAIT" ? (
                    <span className={`ko-ins-side ${play.side === "CE" ? "text-ce" : play.side === "PE" ? "text-pe" : "text-muted"}`}>
                      {play.side === "BOTH" ? "BOTH" : play.side}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="ko-body">
        <div className="ko-desk" data-tab={tab}>
          <div className="ko-main">
            {now && status ? (
              <NowBoard
                status={status}
                now={now}
                grade={liveGrade}
                viewingIso={iso}
                sessionPnl={tally.directional ? tally.pnl : null}
                onOpenSession={(date) => {
                  applyIso(date);
                  setTab("session");
                }}
                onOpenWindow={(slot) => {
                  applyIso(status.sessionIso);
                  setTab("session");
                  setOpenKey(slotKey(slot));
                }}
              />
            ) : null}

            {tab !== "month" ? (
              <div className="ko-session">
                <PlaybookStrip book={book} onPick={pickSlot} nowMin={sameDay ? nowMin : null} />
                <p className="ko-sub">
                  <button type="button" className="ko-link" onClick={() => setNotes((v) => !v)}>
                    {notes ? "Hide notes" : "Notes"}
                  </button>
                  {tally.directional ? (
                    <span className="ko-tally">
                      {tally.hits}/{tally.directional} hit
                      {tally.sits ? ` · ${tally.sits} sit` : ""}
                      {" · "}
                      <span className={tally.pnl >= 0 ? "text-up" : "text-down"}>
                        {tally.pnl >= 0 ? "+" : ""}
                        {tally.pnl.toFixed(0)}
                      </span>
                    </span>
                  ) : tapeLoading ? (
                    <span className="ko-tally text-muted">Tape…</span>
                  ) : tapeError ? (
                    <span className="ko-tally text-muted">{tapeError}</span>
                  ) : null}
                </p>
                {notes ? <PlaybookNotes book={book} /> : null}
                <SessionStrip
                  slots={clockRows}
                  iso={iso}
                  tape={tape}
                  nowMin={nowMin}
                  sameDay={sameDay}
                  grades={grades}
                  onPick={pickSlot}
                />
                <ClockList
                  rows={clockRows}
                  grades={grades}
                  loading={tapeLoading}
                  openKey={openKey}
                  earlierOpen={earlierOpen}
                  laterOpen={laterOpen}
                  onEarlier={() => setEarlierOpen((v) => !v)}
                  onLater={() => setLaterOpen((v) => !v)}
                  onToggle={(key) => setOpenKey((k) => (k === key ? null : key))}
                />
              </div>
            ) : null}
          </div>

          <aside className="ko-rail" aria-label={`${month.label} calendar`}>
            <div className="ko-rail-head">
              <button type="button" className="ko-link" onClick={() => shiftMonth(-1)} aria-label="Previous month">
                ‹
              </button>
              <span>{month.label}</span>
              <button type="button" className="ko-link" onClick={() => shiftMonth(1)} aria-label="Next month">
                ›
              </button>
            </div>
            <MonthHeat month={month} iso={iso} onPick={pickDay} />
          </aside>
        </div>
      </div>
    </div>
    </div>
  );
}

function ClockList({
  rows,
  grades,
  loading,
  openKey,
  earlierOpen,
  laterOpen,
  onEarlier,
  onLater,
  onToggle,
}: {
  rows: WindowSlot[];
  grades: Map<string, SlotGrade>;
  loading: boolean;
  openKey: string | null;
  earlierOpen: boolean;
  laterOpen: boolean;
  onEarlier: () => void;
  onLater: () => void;
  onToggle: (key: string) => void;
}) {
  const spent = rows.filter((s) => s.isPast && !s.isLive);
  const live = rows.filter((s) => s.isLive);
  const upcoming = rows.filter((s) => !s.isPast && !s.isLive);
  const next = upcoming[0] ? [upcoming[0]] : [];
  const later = upcoming.slice(1);
  const spentLabel = live.length === 0 && upcoming.length === 0 ? `Session · ${spent.length}` : `Earlier · ${spent.length}`;

  const renderItem = (slot: WindowSlot) => (
    <ClockItem
      key={slotKey(slot)}
      slot={slot}
      grade={grades.get(slotKey(slot))}
      loading={loading}
      open={openKey === slotKey(slot)}
      onToggle={() => onToggle(slotKey(slot))}
    />
  );

  return (
    <div className="ko-acc">
      {spent.length > 0 ? (
        <div className="ko-acc-group">
          <button type="button" className="ko-acc-sum" aria-expanded={earlierOpen} onClick={onEarlier}>
            {spentLabel}
            <span className="ko-acc-chev" aria-hidden>
              {earlierOpen ? "▾" : "▸"}
            </span>
          </button>
          {earlierOpen ? spent.map(renderItem) : null}
        </div>
      ) : null}
      {live.map(renderItem)}
      {next.map(renderItem)}
      {later.length > 0 ? (
        <div className="ko-acc-group">
          <button type="button" className="ko-acc-sum" aria-expanded={laterOpen} onClick={onLater}>
            Later · {later.length}
            <span className="ko-acc-chev" aria-hidden>
              {laterOpen ? "▾" : "▸"}
            </span>
          </button>
          {laterOpen ? later.map(renderItem) : null}
        </div>
      ) : null}
    </div>
  );
}

function ClockItem({
  slot,
  grade,
  loading,
  open,
  onToggle,
}: {
  slot: WindowSlot;
  grade?: SlotGrade;
  loading: boolean;
  open: boolean;
  onToggle: () => void;
}) {
  const tone = actionTone(slot.action, slot.side);
  const mins = slot.toMin - slot.fromMin;
  const kalam = [slot.kalam.rahu ? "Rahu" : null, slot.kalam.yamagandam ? "Yama" : null, slot.kalam.gulika ? "Gulika" : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="ko-acc-item" data-live={slot.isLive} data-on={open}>
      <button type="button" className="ko-acc-head" aria-expanded={open} onClick={onToggle}>
        <span className="ko-acc-time">
          {slot.from}–{slot.to}
        </span>
        {slot.isLive ? <span className="ko-tag ko-tag-now">NOW</span> : null}
        <span className={sideClass(slot.side)}>{sideLabel(slot.side)}</span>
        <span className={`ko-acc-play ${tone}`}>{slot.action}</span>
        <span className="ko-acc-result">
          <GradeMark grade={grade} loading={loading} />
        </span>
        <span className="ko-acc-chev" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open ? (
        <div className="ko-acc-body">
          {slot.isLive ? null : <p>{slot.suggestion}</p>}
          <p className={slot.isLive ? "" : "text-muted"}>{slot.why}</p>
          <p className="ko-acc-meta">
            {mins}m · {slot.hora} hora
            {kalam ? ` · ${kalam}` : ""}
          </p>
        </div>
      ) : null}
    </div>
  );
}
