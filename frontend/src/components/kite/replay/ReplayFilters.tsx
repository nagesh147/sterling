import React, { useRef, useState } from 'react';
import { useReplayState, useReplayStore } from '../../../hooks/useReplayStore';
import { ReplayPopover } from './primitives/ReplayPopover';
import { MONEYNESS_LEGS, REPLAY_STRATEGIES, strategyLabel } from './replayStrategies';
import * as Icons from './ReplayIcons';

/**
 * Strategy and option-leg filters.
 *
 * Real checkboxes inside labels, not `☑`/`☐` glyphs inside buttons, so keyboard
 * operation and screen-reader semantics come for free. Active narrowings also
 * surface as dismissible chips in the view bar — the previous trigger said
 * "STRAT (2)", which tells you a count but not which two.
 */
export function ReplayFilters() {
  const draft = useReplayStore((s) => s.draft);
  const toggleStrategy = useReplayStore((s) => s.toggleStrategy);
  const toggleMoneyness = useReplayStore((s) => s.toggleMoneyness);
  const setDraft = useReplayStore((s) => s.setDraft);
  const state = useReplayState();
  const [open, setOpen] = useState(false);
  const anchor = useRef<HTMLButtonElement>(null);

  const allStrategies = draft.strategies.includes('all');
  const allLegs = draft.moneyness.includes('ALL');
  const narrowed = (allStrategies ? 0 : draft.strategies.length) + (allLegs ? 0 : draft.moneyness.length);
  const locked = state !== 'idle';

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
        title={locked ? 'Stop the replay to change filters' : 'Filter strategies and option legs'}
        data-testid="replay-filters-trigger"
      >
        <Icons.Filter size={13} />
        Filters
        {narrowed > 0 && <span className="rd-seg-count">{narrowed}</span>}
        <Icons.ChevronDown size={11} />
      </button>

      <ReplayPopover
        open={open}
        onOpenChange={setOpen}
        label="Filter strategies and legs"
        anchorRef={anchor}
        width={280}
      >
        <div className="rd-pop-section">
          <div className="rd-pop-head">
            Strategies
            <span className="rd-pop-head-actions">
              <button
                type="button"
                className="rd-btn rd-btn-sm"
                data-variant="ghost"
                onClick={() => setDraft({ strategies: ['all'] })}
              >
                All
              </button>
            </span>
          </div>
          {REPLAY_STRATEGIES.map((s) => (
            <label className="rd-opt" key={s.id}>
              <input
                type="checkbox"
                checked={allStrategies || draft.strategies.includes(s.id)}
                onChange={() => toggleStrategy(s.id)}
              />
              <span style={{ color: s.tone, display: 'inline-flex' }}>
                <span className="rd-dot-tone" />
              </span>
              <span>{s.label}</span>
            </label>
          ))}
        </div>

        <div className="rd-pop-section">
          <div className="rd-pop-head">
            Option legs
            <span className="rd-pop-head-actions">
              <button
                type="button"
                className="rd-btn rd-btn-sm"
                data-variant="ghost"
                onClick={() => setDraft({ moneyness: ['ALL'] })}
              >
                All
              </button>
            </span>
          </div>
          <div className="rd-opt-legs">
            {MONEYNESS_LEGS.map((leg) => (
              <label className="rd-opt" key={leg.id} style={{ width: 'auto' }} title={leg.hint}>
                <input
                  type="checkbox"
                  checked={allLegs || draft.moneyness.includes(leg.id)}
                  onChange={() => toggleMoneyness(leg.id)}
                />
                <span>{leg.label}</span>
              </label>
            ))}
          </div>
        </div>
      </ReplayPopover>
    </>
  );
}

/** The applied narrowings, so the user can see WHAT is filtered, not just how many. */
export function ReplayFilterChips() {
  const draft = useReplayStore((s) => s.draft);
  const toggleStrategy = useReplayStore((s) => s.toggleStrategy);
  const toggleMoneyness = useReplayStore((s) => s.toggleMoneyness);
  const state = useReplayState();

  const strategies = draft.strategies.includes('all') ? [] : draft.strategies;
  const legs = draft.moneyness.includes('ALL') ? [] : draft.moneyness;
  if (!strategies.length && !legs.length) return null;

  return (
    <span className="rd-filter-chips" data-testid="replay-filter-chips">
      {strategies.map((id) => (
        <span className="rd-filter-chip" key={id}>
          {strategyLabel(id)}
          <button
            type="button"
            disabled={state !== 'idle'}
            aria-label={`Remove ${strategyLabel(id)} filter`}
            onClick={() => toggleStrategy(id)}
          >
            <Icons.Close size={9} />
          </button>
        </span>
      ))}
      {legs.map((id) => (
        <span className="rd-filter-chip" key={id}>
          {id}
          <button
            type="button"
            disabled={state !== 'idle'}
            aria-label={`Remove ${id} leg filter`}
            onClick={() => toggleMoneyness(id)}
          >
            <Icons.Close size={9} />
          </button>
        </span>
      ))}
    </span>
  );
}
