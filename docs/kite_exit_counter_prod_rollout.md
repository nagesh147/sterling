# Sterling Kite Engine Exit Counter - Production Rollout Notes

## Overview
The exit logic for auto-exec positions now uses a configurable `exit_mode` (default: `two_red`):
- Entry: fresh full 3 ST green alignment + green arrow on 1H HA.
- Exit: counter based on red ST lines (1/2/3 or 3 + fresh counter red arrow) + adaptive trailing SL on best remaining green line.
- Health exposed: `current_red_count` / `exit_threshold` per open position.
- Monitor (`on_tick`) now respects red count in addition to price trail breach.

This unifies the "directional 3-line" entry/exit counter for options scalping.

## Changes & Migration
- Default changed from hard-coded "one_red" (tight) to "two_red" (balanced).
- Per-position `exit_mode` persisted at entry time (remembers your choice).
- Old positions (pre-change) default to engine config at scan time for health; explicit mode saved for new.
- Backward compat: positions API, monitor, scanner all handle missing fields gracefully (default 0 / one_red).
- No data loss on restart (DB persisted via kite_engine_positions_{uid}).

## Rollout Steps
1. **Paper first (recommended)**:
   - Set `auto_execute: false` in user config.
   - Observe signals + open-positions health via UI / API.
   - Use `POST /api/v1/kite/engine/config` to test modes per user.

2. **Enable gradually**:
   - Start with small universe / low risk_pct.
   - Monitor logs for "red count exit", "Trail updated", "Red count hit".
   - Watch /open-positions for current_red_count nearing threshold.

3. **Prod enable**:
   - Deploy with default "two_red".
   - Per-account opt-in via config (exit_mode, auto_execute).
   - Update risk sizing if needed (tighter modes may increase trade frequency).

4. **Verification**:
   - Run engine tests + scanner tests.
   - End-to-end: fresh entry → crash → observe red health → exit with correct reason.
   - Check SetupChart shows exit viz and mode.

## Monitoring & Observability
- **Logs**:
  - "red count exit X/Y (mode)"
  - "Red count hit ... — monitor will consider"
  - "Trail updated ... (reds implied)"
- **API**:
  - GET /api/v1/kite/engine/open-positions → current_red_count, exit_threshold, exit_mode
  - GET /api/v1/kite/engine/signals → is_active reflects mode
- **Metrics/Stats**: existing session stats + custom alerts on high red exits.
- **Dash**: EnginePositionsPane now shows health column + badges.
- Watch for:
  - Over-exits on chop (use two_red+).
  - Missed exits (three_red_signal in trends).

## Risks & Mitigations
- **Over-sensitive exits (one_red)**: more whipsaws, higher costs. Mit: default two_red, user choice.
- **Holding too long (three_red)**: bigger drawdowns. Mit: adaptive trail + three_red_signal option.
- **Signal mode mismatch**: entry under one cfg, exit under another. Mit: persist per-position mode.
- **Live data lag**: reds from 5m scans, intrabar via price trail. Mit: monitor dual check.
- **Options theta bleed**: tight modes bank faster. Mit: docs recommend.
- **Futures vs options**: direction handling tested.
- **Restart**: health recomputed on next scan.

Rollback: set exit_mode=one_red (or previous), no code change needed. Monitor will use new health on next tick/scan.

## Testing & Validation
- Unit: test_engine (all modes in manage), test_scanner (is_active), test_risk_and_monitor (red in on_tick).
- Integration: scan_user → _update health → monitor on_tick red exit.
- Prod canary: enable for 1-2 accounts, small size, review exit reasons after 1 week.
- Backtest: use existing backtest with exit_mode param.

## Future / Deeper Unification
- Shared exit_counter.py used by kite + directional.
- Directional engine can adopt exit_mode for its st_trends (fake 3-line).
- Common health exposure in non-kite positions.
- Config UI for per-underlying overrides.
- See design spec for 3ST counter unification notes.

Contact: update via PR, test in paper before prod.

## References
- engine.py:manage, regime.py:red_line_count
- monitor.py:on_tick red check
- config.py, schemas.py
- test_*.py for red paths
- docs/superpowers/specs/2026-06-13-kite-triple-supertrend-engine-design.md
