import React, { useMemo, useRef, useState } from 'react';
import { useReplayState, useReplayStore } from '../../../hooks/useReplayStore';
import { getDynamicMarketPresets } from '../../../lib/replay/marketSessions';
import { ReplayPopover } from './primitives/ReplayPopover';
import { fmtSessionDate, fmtTime } from './replayFormat';
import { useAvailableDates, verdictForDate } from './useAvailableDates';
import * as Icons from './ReplayIcons';

const HOUR_RANGES = [
  { id: 'full', label: 'Full session', start: '09:00:00', end: '15:30:00' },
  { id: 'regular', label: 'Regular', start: '09:15:00', end: '15:30:00' },
  { id: 'first', label: 'First hour', start: '09:15:00', end: '10:15:00' },
  { id: 'last', label: 'Last hour', start: '14:30:00', end: '15:30:00' },
];

/**
 * Session date, range and market hours.
 *
 * One disabled entry point while a replay runs, rather than the nineteen
 * individually-disabled controls the previous configuration tab carried.
 */
export function ReplaySessionPicker({ widthBucket }: { widthBucket: string }) {
  const draft = useReplayStore((s) => s.draft);
  const setDraft = useReplayStore((s) => s.setDraft);
  const state = useReplayState();
  const [open, setOpen] = useState(false);
  const anchor = useRef<HTMLButtonElement>(null);

  const { data: available } = useAvailableDates();
  const presets = useMemo(() => getDynamicMarketPresets(), []);
  const verdict = verdictForDate(draft.date, available);
  const rangeInvalid = draft.endDate < draft.date;
  const timesInvalid = draft.endTime <= draft.startTime;

  const locked = state !== 'idle';

  const label =
    widthBucket === 'sm'
      ? fmtSessionDate(draft.date, true)
      : widthBucket === 'lg' || widthBucket === 'md'
        ? fmtSessionDate(draft.date, true)
        : `${fmtSessionDate(draft.date)} · ${fmtTime(draft.startTime, 5)}–${fmtTime(draft.endTime, 5)}`;

  const applyPreset = (date: string) => setDraft({ date, endDate: date });

  return (
    <>
      <button
        type="button"
        ref={anchor}
        className="rd-btn"
        disabled={locked}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        title={locked ? 'Stop the replay to change the session' : 'Choose the replay session'}
        data-testid="replay-session-trigger"
      >
        <Icons.Calendar size={13} />
        {label}
        <Icons.ChevronDown size={11} />
      </button>

      <ReplayPopover
        open={open}
        onOpenChange={setOpen}
        label="Choose replay session"
        anchorRef={anchor}
        width={320}
      >
        <div className="rd-pop-section">
          <div className="rd-pop-head">Quick</div>
          {presets.map((p) => (
            <label className="rd-opt" key={p.id}>
              <input
                type="radio"
                name="rd-session-preset"
                checked={draft.date === p.date}
                onChange={() => applyPreset(p.date)}
              />
              <span>{p.label}</span>
              <span className="rd-opt-hint">{fmtSessionDate(p.date, true)}</span>
            </label>
          ))}
        </div>

        <div className="rd-pop-section">
          <div className="rd-pop-head">Session date</div>
          <div className="rd-grid-2">
            <div className="rd-field">
              <label className="rd-field-label" htmlFor="rd-date-start">Start</label>
              <input
                id="rd-date-start"
                type="date"
                className="rd-input"
                value={draft.date}
                min={available?.earliest ?? undefined}
                max={available?.latest ?? undefined}
                onChange={(e) => setDraft({ date: e.target.value, endDate: e.target.value })}
              />
            </div>
            <div className="rd-field">
              <label className="rd-field-label" htmlFor="rd-date-end">End (range)</label>
              <input
                id="rd-date-end"
                type="date"
                className="rd-input"
                value={draft.endDate}
                min={draft.date}
                max={available?.latest ?? undefined}
                aria-invalid={rangeInvalid}
                aria-describedby={rangeInvalid ? 'rd-range-err' : undefined}
                onChange={(e) => setDraft({ endDate: e.target.value })}
              />
            </div>
          </div>
          {rangeInvalid && (
            <div className="rd-field-error" id="rd-range-err">End date is before the start date.</div>
          )}
          {verdict.level === 'warn' && <div className="rd-field-warn">{verdict.message}</div>}
          {verdict.level === 'error' && <div className="rd-field-error">{verdict.message}</div>}
        </div>

        <div className="rd-pop-section">
          <div className="rd-pop-head">Market hours</div>
          <div className="rd-grid-2">
            <div className="rd-field">
              <label className="rd-field-label" htmlFor="rd-time-start">From</label>
              <input
                id="rd-time-start"
                type="time"
                step={1}
                className="rd-input"
                value={draft.startTime}
                onChange={(e) => setDraft({ startTime: e.target.value })}
              />
            </div>
            <div className="rd-field">
              <label className="rd-field-label" htmlFor="rd-time-end">To</label>
              <input
                id="rd-time-end"
                type="time"
                step={1}
                className="rd-input"
                value={draft.endTime}
                aria-invalid={timesInvalid}
                onChange={(e) => setDraft({ endTime: e.target.value })}
              />
            </div>
          </div>
          {timesInvalid && <div className="rd-field-error">End time must be after the start time.</div>}
          <div className="rd-chip-row" style={{ marginTop: 8 }}>
            {HOUR_RANGES.map((r) => (
              <button
                key={r.id}
                type="button"
                className="rd-btn rd-btn-sm"
                data-variant={draft.startTime === r.start && draft.endTime === r.end ? 'primary' : undefined}
                onClick={() => setDraft({ startTime: r.start, endTime: r.end })}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      </ReplayPopover>
    </>
  );
}
