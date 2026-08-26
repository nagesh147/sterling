import React, { useEffect, useMemo, useState } from 'react';
import { k, tint } from '../../styles/kiteUI';
import { forecastDay, forecastMonth } from '../../lib/astro/engine';
import { formatIstDate, formatIstIsoDate, getIstParts, utcFromIstParts } from '../../lib/astro/time';
import { UNDERLYINGS, type GapKind, type Regime, type TradeAction, type TradeSide, type Underlying, type WindowSlot } from '../../lib/astro/types';

function todayIso(): string {
  return formatIstIsoDate(new Date());
}

function shiftIso(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number);
  const dt = utcFromIstParts(y, m, d, 12, 0, 0);
  dt.setUTCDate(dt.getUTCDate() + days);
  return formatIstIsoDate(dt);
}

function isoToDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return utcFromIstParts(y, m, d, 9, 0, 0);
}

function regimeColor(regime: Regime): string {
  if (regime.includes('Positive')) return 'var(--k-green)';
  if (regime.includes('Negative')) return 'var(--k-red)';
  return 'var(--k-amber)';
}

function gapColor(kind: GapKind): string {
  if (kind === 'up') return 'var(--k-green)';
  if (kind === 'down') return 'var(--k-red)';
  return 'var(--k-amber)';
}

function actionColor(action: TradeAction, side: TradeSide): string {
  if (action === 'AVOID' || action === 'WAIT') return 'var(--k-ink-4)';
  if (side === 'CE') return 'var(--k-green)';
  if (side === 'PE') return 'var(--k-red)';
  return 'var(--k-amber)';
}

const pill: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  fontSize: 10,
  fontWeight: 600,
  letterSpacing: '0.04em',
  padding: '2px 6px',
  borderRadius: 3,
  background: 'var(--k-surface-2)',
  color: 'var(--k-ink-3)',
};

export function AstroPane() {
  const [iso, setIso] = useState(todayIso);
  const [underlying, setUnderlying] = useState<Underlying>('NIFTY');
  const [view, setView] = useState<'net' | 'thirty'>('net');
  const [now, setNow] = useState<Date | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [monthCursor, setMonthCursor] = useState(() => {
    const p = getIstParts(new Date());
    return { year: p.year, month: p.month };
  });

  useEffect(() => {
    setNow(new Date());
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const dayDate = useMemo(() => isoToDate(iso), [iso]);
  const book = useMemo(() => forecastDay(dayDate, underlying, now ?? dayDate), [dayDate, underlying, now]);
  const month = useMemo(
    () => forecastMonth(monthCursor.year, monthCursor.month, underlying, now ?? dayDate),
    [monthCursor, underlying, now, dayDate],
  );

  const rows = view === 'net' ? book.netResults : book.slots;
  const live = book.slots.find((s) => s.isLive) ?? null;
  const dateLabel = formatIstDate(dayDate);
  const selected = rows.find((s) => `${s.from}-${s.to}` === selectedKey) ?? live ?? null;
  const remaining = live && now
    ? Math.max(0, live.toMin * 60 - (getIstParts(now).hour * 3600 + getIstParts(now).minute * 60 + getIstParts(now).second))
    : 0;
  const remainLabel = live
    ? `${String(Math.floor(remaining / 60)).padStart(2, '0')}:${String(remaining % 60).padStart(2, '0')}`
    : null;

  return (
    <div style={{ width: '100%', height: '100%', overflow: 'auto', background: 'var(--k-surface-sunken-2)', fontFamily: k.fontFamily, color: k.text }}>
      <style>{`@media (max-width: 860px) { .astro-hero { grid-template-columns: 1fr !important; } }`}</style>
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '22px 22px 48px', display: 'flex', flexDirection: 'column', gap: 18 }}>
        <header style={{ display: 'flex', flexWrap: 'wrap', gap: 14, justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div style={{ minWidth: 0, maxWidth: 720 }}>
            <div style={{ fontSize: 11, fontWeight: 650, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--k-brand)' }}>Financial astrology</div>
            <h1 style={{ margin: '6px 0 0', fontSize: 26, fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--k-ink-1)' }}>
              Opening gap, 30-minute clock, month book
            </h1>
            <p style={{ margin: '8px 0 0', fontSize: 13, lineHeight: 1.55, color: 'var(--k-ink-5)' }}>
              Sidereal Lahiri at Mumbai. Day thesis first (fade / trend / chop), then hora, choghadiya, Rahu Kalam, sector lords. No candles, no OI — the same date always reprints the same book.
            </p>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
            <select
              value={underlying}
              onChange={(e) => setUnderlying(e.target.value as Underlying)}
              style={ctrl}
            >
              {UNDERLYINGS.map((u) => (
                <option key={u.id} value={u.id}>{u.label}</option>
              ))}
            </select>
            <div style={{ display: 'flex', height: 36, border: `1px solid ${k.border}`, borderRadius: 6, background: k.surface }}>
              <button type="button" aria-label="Previous session" onClick={() => setIso(shiftIso(iso, -1))} style={iconBtn}>‹</button>
              <input
                type="date"
                value={iso}
                onChange={(e) => {
                  if (!e.target.value) return;
                  setIso(e.target.value);
                  const [y, m] = e.target.value.split('-').map(Number);
                  setMonthCursor({ year: y, month: m });
                }}
                style={{ ...ctrl, border: 0, width: 148, height: 34 }}
              />
              <button type="button" aria-label="Next session" onClick={() => setIso(shiftIso(iso, 1))} style={iconBtn}>›</button>
            </div>
            <button
              type="button"
              onClick={() => {
                const t = todayIso();
                setIso(t);
                const p = getIstParts(new Date());
                setMonthCursor({ year: p.year, month: p.month });
              }}
              style={ctrl}
            >
              Today
            </button>
          </div>
        </header>

        <section className="astro-hero" style={{ display: 'grid', gap: 12, gridTemplateColumns: 'minmax(0,1.4fr) minmax(260px,1fr)' }}>
          <div style={card}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <div>
                <div style={meta}>Pre-open gap call · {dateLabel} · {book.panchang.weekday}</div>
                <div style={{ marginTop: 10, fontSize: 42, fontWeight: 750, letterSpacing: '-0.04em', lineHeight: 1, color: gapColor(book.gap.kind) }}>
                  {book.gap.label}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 22 }}>{book.gap.confidence}</div>
                <div style={{ fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--k-ink-5)' }}>confidence</div>
              </div>
            </div>
            <p style={{ margin: '14px 0 0', fontSize: 14, lineHeight: 1.55, color: 'var(--k-ink-2)' }}>{book.gap.summary}</p>
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              <span style={pill}>{book.gap.openAction}</span>
              <span style={{ ...pill, color: 'var(--k-ink-1)', background: tint('var(--k-brand)', 16) }}>{book.gap.thesis.replace('-', ' ')}</span>
              <span style={pill}>{book.gap.volatility} vol</span>
              <span style={pill}>{book.gap.bias}</span>
              <span style={pill}>{book.gap.horaAtOpen} hora</span>
              <span style={pill}>{book.panchang.tithiName} · {book.panchang.paksha}</span>
              <span style={pill}>{book.panchang.nakshatra} p{book.panchang.nakshatraPada}</span>
              <span style={pill}>Lagna {book.panchang.lagnaSign}</span>
              {book.gap.eclipse && <span style={{ ...pill, color: 'var(--k-red)', background: tint('var(--k-red)', 12) }}>Eclipse corridor</span>}
              {book.gap.gandanta && <span style={{ ...pill, color: 'var(--k-amber)', background: tint('var(--k-amber)', 12) }}>Gandanta</span>}
            </div>
            <p style={{ margin: '14px 0 0', paddingTop: 14, borderTop: `1px solid ${k.border}`, fontSize: 13, lineHeight: 1.55, color: 'var(--k-ink-5)' }}>
              {book.gap.firstHourNote}
            </p>
            <p style={{ margin: '8px 0 0', fontSize: 12.5, lineHeight: 1.5, color: 'var(--k-ink-5)' }}>{book.gap.thesisNote}</p>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={card}>
              <div style={meta}>This window</div>
              {live ? (
                <>
                  <div style={{ marginTop: 8, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 13 }}>{live.from} – {live.to}</div>
                  <div style={{ marginTop: 4, fontSize: 20, fontWeight: 700, color: regimeColor(live.regime) }}>{live.regime}</div>
                  <div style={{ marginTop: 2, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 15, fontWeight: 700, color: actionColor(live.action, live.side) }}>{live.action}</div>
                  <p style={{ margin: '8px 0 0', fontSize: 13, lineHeight: 1.45, color: 'var(--k-ink-5)' }}>{live.suggestion}</p>
                  {remainLabel && <p style={{ margin: '10px 0 0', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 11, color: 'var(--k-ink-5)' }}>Ends in {remainLabel}</p>}
                </>
              ) : (
                <p style={{ margin: '8px 0 0', fontSize: 13, lineHeight: 1.5, color: 'var(--k-ink-5)' }}>{book.playbook.headline}</p>
              )}
            </div>
            <div style={card}>
              <div style={meta}>Day playbook</div>
              <ul style={{ margin: '10px 0 0', padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                <li><span style={{ color: 'var(--k-ink-5)' }}>Thesis · </span>{book.gap.thesis.replace('-', ' ')}</li>
                <li><span style={{ color: 'var(--k-ink-5)' }}>Best CE · </span><span style={{ color: 'var(--k-green)' }}>{book.playbook.bestCe ? `${book.playbook.bestCe.from}–${book.playbook.bestCe.to} · ${book.playbook.bestCe.product}` : 'no clean CE slot'}</span></li>
                <li><span style={{ color: 'var(--k-ink-5)' }}>Best PE · </span><span style={{ color: 'var(--k-red)' }}>{book.playbook.bestPe ? `${book.playbook.bestPe.from}–${book.playbook.bestPe.to} · ${book.playbook.bestPe.product}` : 'no clean PE slot'}</span></li>
                <li><span style={{ color: 'var(--k-ink-5)' }}>Sit out · </span>{book.playbook.avoid.length ? book.playbook.avoid.map((s) => `${s.from}–${s.to}`).join(', ') : 'no Rahu Kalam overlap'}</li>
                <li><span style={{ color: 'var(--k-ink-5)' }}>Close · </span><span style={{ color: regimeColor(book.playbook.closeBias) }}>{book.playbook.closeBias}</span></li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <div style={meta}>Session tape 09:15–15:30</div>
          <div style={{ marginTop: 8, display: 'flex', height: 32, overflow: 'hidden', border: `1px solid ${k.border}`, borderRadius: 6 }}>
            {book.slots.map((s) => {
              const w = ((s.toMin - s.fromMin) / (15 * 60 + 30 - 9 * 60 - 15)) * 100;
              return (
                <button
                  key={`${s.from}-${s.to}`}
                  type="button"
                  title={`${s.from}–${s.to} ${s.regime} · ${s.action}`}
                  onClick={() => { setView('thirty'); setSelectedKey(`${s.from}-${s.to}`); }}
                  style={{
                    width: `${w}%`,
                    minWidth: 0,
                    border: 0,
                    padding: 0,
                    cursor: 'pointer',
                    background: regimeColor(s.regime),
                    opacity: s.isLive ? 1 : 0.78,
                    boxShadow: s.isLive ? 'inset 0 0 0 2px rgba(0,0,0,.35)' : undefined,
                  }}
                />
              );
            })}
          </div>
          <div style={{ marginTop: 4, display: 'flex', justifyContent: 'space-between', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 10, color: 'var(--k-ink-5)' }}>
            <span>9:15</span><span>12:15</span><span>3:30</span>
          </div>
        </section>

        <section>
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: 10, alignItems: 'flex-end', marginBottom: 10 }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, letterSpacing: '-0.02em' }}>Intraday timings</h2>
              <p style={{ margin: '4px 0 0', fontSize: 12.5, color: 'var(--k-ink-5)' }}>
                {view === 'net' ? 'Merged net results — consecutive identical horas collapsed.' : 'Raw 30-minute clock, 13 slots from 9:15 to 3:30.'}
              </p>
            </div>
            <div style={{ display: 'flex', border: `1px solid ${k.border}`, borderRadius: 6, padding: 2 }}>
              {(['net', 'thirty'] as const).map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setView(id)}
                  style={{
                    height: 32,
                    padding: '0 12px',
                    border: 0,
                    borderRadius: 4,
                    cursor: 'pointer',
                    background: view === id ? 'var(--k-surface-2)' : 'transparent',
                    color: view === id ? 'var(--k-ink-1)' : 'var(--k-ink-5)',
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  {id === 'net' ? 'Net results' : 'Every 30 min'}
                </button>
              ))}
            </div>
          </div>

          {view === 'net' ? (
            <div style={{ overflowX: 'auto', border: `1px solid ${k.border}`, borderRadius: 10, background: k.surface }}>
              <table style={{ width: '100%', minWidth: 640, borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ background: 'var(--k-surface-2)', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--k-ink-5)' }}>
                    <th style={th}>Date</th>
                    <th style={th}>From</th>
                    <th style={th}>To</th>
                    <th style={th}>Timings net results</th>
                    <th style={th}>Play</th>
                    <th style={th}>Suggestion</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((slot) => {
                    const key = `${slot.from}-${slot.to}`;
                    const on = selectedKey === key || slot.isLive;
                    return (
                      <tr
                        key={key}
                        onClick={() => setSelectedKey(key)}
                        style={{ cursor: 'pointer', background: on ? tint('var(--k-brand)', 8) : 'transparent', borderTop: `1px solid ${k.border}` }}
                      >
                        <td style={tdMono}>{dateLabel}</td>
                        <td style={tdMono}>{slot.from}</td>
                        <td style={tdMono}>{slot.to}</td>
                        <td style={{ ...td, fontWeight: 650, color: regimeColor(slot.regime) }}>
                          {slot.regime}
                          <div style={{ fontWeight: 400, fontSize: 11, color: 'var(--k-ink-5)', marginTop: 2 }}>
                            {slot.hora} hora · {slot.choghadiya}{slot.kalam.rahu ? ' · Rahu Kalam' : ''}
                          </div>
                        </td>
                        <td style={{ ...tdMono, fontWeight: 700, color: actionColor(slot.action, slot.side) }}>{slot.action}</td>
                        <td style={{ ...td, fontSize: 12.5, color: 'var(--k-ink-4)', maxWidth: 360 }}>{slot.suggestion}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {rows.map((slot) => (
                <SlotCard key={`${slot.from}-${slot.to}`} slot={slot} selected={`${slot.from}-${slot.to}` === selectedKey} onSelect={() => setSelectedKey(`${slot.from}-${slot.to}`)} />
              ))}
            </div>
          )}
          {selected && view === 'net' && (
            <div style={{ ...card, marginTop: 10, padding: '12px 14px' }}>
              <div style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 11, color: 'var(--k-ink-5)' }}>{selected.from}–{selected.to} · {selected.product}</div>
              <div style={{ marginTop: 4, fontSize: 13, lineHeight: 1.5 }}>{selected.suggestion}</div>
              <div style={{ marginTop: 4, fontSize: 11, color: 'var(--k-ink-5)' }}>{selected.why}</div>
            </div>
          )}
        </section>

        <section>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-end', marginBottom: 10 }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>{month.label} projection</h2>
              <p style={{ margin: '4px 0 0', fontSize: 12.5, color: 'var(--k-ink-5)' }}>{month.summary}</p>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button type="button" aria-label="Previous month" onClick={() => setMonthCursor((c) => c.month === 1 ? { year: c.year - 1, month: 12 } : { year: c.year, month: c.month - 1 })} style={{ ...ctrl, width: 36, padding: 0 }}>‹</button>
              <button type="button" aria-label="Next month" onClick={() => setMonthCursor((c) => c.month === 12 ? { year: c.year + 1, month: 1 } : { year: c.year, month: c.month + 1 })} style={{ ...ctrl, width: 36, padding: 0 }}>›</button>
            </div>
          </div>
          <MonthGrid month={month} selected={iso} onSelect={setIso} />
        </section>

        <section style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          <div style={card}>
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 700 }}>Why this open</h3>
            <ol style={{ margin: '10px 0 0', padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
              {book.gap.reasons.map((r, i) => (
                <li key={i} style={{ display: 'flex', gap: 8, fontSize: 13, lineHeight: 1.4 }}>
                  <span style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 10, color: 'var(--k-ink-5)' }}>{String(i + 1).padStart(2, '0')}</span>
                  <span>{r}</span>
                </li>
              ))}
            </ol>
            {book.gap.yogas.length > 0 && (
              <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${k.border}` }}>
                <div style={meta}>Yogas</div>
                <ul style={{ margin: '8px 0 0', padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {book.gap.yogas.map((y) => <li key={y} style={{ fontSize: 12.5, lineHeight: 1.4 }}>{y}</li>)}
                </ul>
              </div>
            )}
          </div>
          <div style={card}>
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 700 }}>Sidereal board · 09:00 IST</h3>
            <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: '2px 14px' }}>
              {book.planets.map((p) => (
                <div key={p.name} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, padding: '6px 0', borderBottom: `1px solid ${k.border}`, fontSize: 12 }}>
                  <span style={{ color: 'var(--k-ink-5)' }}>{p.name}</span>
                  <span style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 11 }}>
                    {p.sign.slice(0, 3)} {p.degreeInSign.toFixed(1)}°{p.retrograde ? ' R' : ''}
                  </span>
                </div>
              ))}
            </div>
            <p style={{ margin: '10px 0 0', fontSize: 11, color: 'var(--k-ink-5)' }}>
              {book.panchang.yoga} yoga · {book.panchang.karana} karana · {book.panchang.nakshatraLord} rules the Moon
            </p>
            {book.aspects.slice(0, 5).map((a) => (
              <div key={`${a.a}-${a.b}-${a.kind}`} style={{ marginTop: 6, fontSize: 12, color: 'var(--k-ink-4)' }}>
                {a.a} {a.kind} {a.b} <span style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 11, color: 'var(--k-ink-5)' }}>{a.orb.toFixed(1)}°</span>
              </div>
            ))}
          </div>
        </section>

        <p style={{ fontSize: 11, lineHeight: 1.5, color: 'var(--k-ink-5)' }}>
          Research overlay, not a broker signal. Sidereal Lahiri at Mumbai. Deterministic — a given session always reprints the same gap, windows, and month cells. Not financial advice.
        </p>
      </div>
    </div>
  );
}

function SlotCard({ slot, selected, onSelect }: { slot: WindowSlot; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        display: 'grid',
        gridTemplateColumns: '3px 1fr',
        width: '100%',
        textAlign: 'left',
        border: `1px solid ${slot.isLive ? 'var(--k-brand)' : k.border}`,
        borderRadius: 8,
        background: selected || slot.isLive ? tint('var(--k-brand)', 8) : k.surface,
        overflow: 'hidden',
        cursor: 'pointer',
        padding: 0,
        color: 'inherit',
        fontFamily: 'inherit',
      }}
    >
      <div style={{ background: regimeColor(slot.regime) }} />
      <div style={{ padding: '10px 12px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 12px', alignItems: 'center' }}>
          <span style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 12 }}>{slot.from} – {slot.to}</span>
          {slot.isLive && <span style={{ ...pill, background: 'var(--k-brand)', color: '#fff' }}>Live</span>}
          <span style={{ fontSize: 13, fontWeight: 700, color: regimeColor(slot.regime) }}>{slot.regime}</span>
          <span style={{ marginLeft: 'auto', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 12, fontWeight: 700, color: actionColor(slot.action, slot.side) }}>{slot.action}</span>
        </div>
        <div style={{ marginTop: 6, fontSize: 11, color: 'var(--k-ink-5)' }}>
          Hora {slot.hora} · Lagna {slot.lagna} · {slot.choghadiya} · {slot.product}
        </div>
        <div style={{ marginTop: 6, fontSize: 13, lineHeight: 1.4 }}>{slot.suggestion}</div>
      </div>
    </button>
  );
}

function MonthGrid({
  month,
  selected,
  onSelect,
}: {
  month: ReturnType<typeof forecastMonth>;
  selected: string;
  onSelect: (iso: string) => void;
}) {
  const first = month.days[0];
  const pad = first ? new Date(`${first.date}T12:00:00+05:30`).getDay() : 0;
  const cells: Array<(typeof month.days)[number] | null> = [...Array(pad).fill(null), ...month.days];
  while (cells.length % 7 !== 0) cells.push(null);
  return (
    <div style={{ overflow: 'hidden', border: `1px solid ${k.border}`, borderRadius: 10 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', background: 'var(--k-surface-2)', textAlign: 'center', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--k-ink-5)' }}>
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => <div key={d} style={{ padding: '8px 4px' }}>{d}</div>)}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)' }}>
        {cells.map((day, i) => {
          if (!day) return <div key={`e-${i}`} style={{ minHeight: 74, borderTop: `1px solid ${k.border}` }} />;
          const closed = day.isWeekend || day.isHoliday;
          const g = day.gap;
          const color = g === 'up' ? 'var(--k-green)' : g === 'down' ? 'var(--k-red)' : g === 'flat' ? 'var(--k-amber)' : 'var(--k-ink-5)';
          return (
            <button
              key={day.date}
              type="button"
              disabled={closed}
              onClick={() => onSelect(day.date)}
              style={{
                minHeight: 74,
                border: 0,
                borderTop: `1px solid ${k.border}`,
                borderLeft: `1px solid ${k.border}`,
                background: day.date === selected ? tint('var(--k-brand)', 12) : 'transparent',
                textAlign: 'left',
                padding: 8,
                cursor: closed ? 'default' : 'pointer',
                opacity: closed ? 0.45 : 1,
                color: 'inherit',
                fontFamily: 'inherit',
              }}
            >
              <div style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 11, color: day.isToday ? 'var(--k-brand)' : 'var(--k-ink-5)' }}>{Number(day.date.slice(-2))}</div>
              <div style={{ marginTop: 4, fontSize: 10, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color }}>{closed ? (day.isHoliday ? 'Hol' : '') : g === 'up' ? 'Up' : g === 'down' ? 'Dn' : 'Flat'}</div>
              {!closed && day.openAction && <div style={{ marginTop: 2, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 9, color: 'var(--k-ink-5)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{day.openAction}</div>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

const card: React.CSSProperties = {
  background: k.surface,
  border: `1px solid ${k.border}`,
  borderRadius: 12,
  padding: 18,
};

const meta: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 650,
  letterSpacing: '0.16em',
  textTransform: 'uppercase',
  color: 'var(--k-ink-5)',
};

const ctrl: React.CSSProperties = {
  height: 36,
  border: `1px solid ${k.border}`,
  borderRadius: 6,
  background: k.surface,
  color: k.text,
  padding: '0 10px',
  fontSize: 13,
  fontFamily: 'inherit',
};

const iconBtn: React.CSSProperties = {
  width: 36,
  height: 34,
  border: 0,
  background: 'transparent',
  color: 'var(--k-ink-4)',
  cursor: 'pointer',
  fontSize: 18,
};

const th: React.CSSProperties = { padding: '10px 12px', fontWeight: 650 };
const td: React.CSSProperties = { padding: '10px 12px', fontSize: 13, verticalAlign: 'top' };
const tdMono: React.CSSProperties = { ...td, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 12, whiteSpace: 'nowrap' };
