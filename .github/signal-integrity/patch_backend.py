from pathlib import Path
import os
import subprocess
import sys

SCHEMAS = Path('backend/app/engines/sterling_kite_engine/schemas.py')
SCANNER = Path('backend/app/services/kite_engine/scanner.py')
SERVICE = Path('backend/app/services/kite_engine/service.py')
errors = []


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        errors.append(f'{path}: expected one anchor, found {count}: {old[:100]!r}')
        return
    path.write_text(text.replace(old, new, 1))


replace_once(SCHEMAS,
'''    token: Optional[int] = None
    is_active: bool = False   # this contract's SuperTrend is still aligned on the latest bar
''',
'''    token: Optional[int] = None
    is_active: bool = False   # this contract's SuperTrend is still aligned on the latest bar
    # Contract-local evidence. The grouped parent is a display/sort summary only.
    signal_timestamp_ms: Optional[int] = None
    entry_timestamp_ms: Optional[int] = None
    alignment: Optional[AlignmentChip] = None
    exit_state: Optional[str] = None
''')

replace_once(SCANNER,
'''        leg.premium_spot = r.spot
        leg.premium_sl = r.stop_loss
        leg.token = r.token
        sym_key = (*key, leg.option_symbol)
''',
'''        leg.premium_spot = r.spot
        leg.premium_sl = r.stop_loss
        leg.token = r.token
        leg.signal_timestamp_ms = int(leg.signal_timestamp_ms or r.timestamp_ms)
        leg.entry_timestamp_ms = int(leg.entry_timestamp_ms or r.timestamp_ms)
        leg.alignment = leg.alignment or r.alignment
        leg.exit_state = leg.exit_state or r.exit_state
        sym_key = (*key, leg.option_symbol)
''')

replace_once(SCANNER,
'''            legs=[OptionLeg(moneyness=moneyness, option_type=pick.option_type,
                            option_symbol=pick.option_symbol, strike=pick.strike,
                            expiry=pick.expiry, lot_size=pick.lot_size or None,
                            entry_sl=entry_sl, is_active=active)],
''',
'''            legs=[OptionLeg(moneyness=moneyness, option_type=pick.option_type,
                            option_symbol=pick.option_symbol, strike=pick.strike,
                            expiry=pick.expiry, lot_size=pick.lot_size or None,
                            entry_sl=entry_sl, is_active=active,
                            signal_timestamp_ms=ts, entry_timestamp_ms=ts,
                            alignment=AlignmentChip(fast=int(r.t_fast[i]), mid=int(r.t_mid[i]), slow=int(r.t_slow[i])),
                            exit_state=_exit_state_str(r, "long", last_idx, cfg))],
''')

replace_once(SCANNER,
'''        OptionLeg(moneyness=m, option_type=p.option_type, option_symbol=p.option_symbol,
                  strike=p.strike, expiry=p.expiry, lot_size=p.lot_size or None)
''',
'''        OptionLeg(moneyness=m, option_type=p.option_type, option_symbol=p.option_symbol,
                  strike=p.strike, expiry=p.expiry, lot_size=p.lot_size or None,
                  entry_timestamp_ms=row.timestamp_ms)
''')

replace_once(SCANNER,
'''    if leg is None and row.legs:
        leg = min(row.legs, key=lambda l: abs(l.strike - row.spot))
    if leg is None:
        return None
    return {
''',
'''    if leg is None and row.legs:
        reference_spot = float(row.underlying_spot or row.spot or 0.0)
        leg = min(row.legs, key=lambda l: abs(l.strike - reference_spot))
    if leg is None:
        return None
    return {
''')

replace_once(SCANNER,
'''        "stop_loss": float(row.stop_loss),
''',
'''        "stop_loss": float(leg.premium_sl if leg.premium_sl is not None else row.stop_loss),
''')

replace_once(SCANNER,
'''        if timestamp_ms > 0 and r is not None and r.timestamp_ms != timestamp_ms:
            # token reused across snapshots at different timestamps — exact-match scan
            return next((x for x in self.rows
                         if (getattr(x, "token", None) == token
                             or any(getattr(l, "token", None) == token for l in x.legs))
                         and x.timestamp_ms == timestamp_ms), None)
        return r
''',
'''        if timestamp_ms > 0 and r is not None:
            def _matches(x):
                if getattr(x, "token", None) == token and x.timestamp_ms == timestamp_ms:
                    return True
                return any(
                    getattr(l, "token", None) == token and timestamp_ms in {
                        int(getattr(l, "entry_timestamp_ms", 0) or 0),
                        int(getattr(l, "signal_timestamp_ms", 0) or 0),
                    }
                    for l in x.legs
                )
            if not _matches(r):
                return next((x for x in self.rows if _matches(x)), None)
        return r
''')

replace_once(SCANNER,
'''                ordered = sorted(moneyness, key=lambda m: _MONEYNESS_ORDER.get(m, 99))
                latest_ts = candles[-1].timestamp_ms

                for row in _retain_signals(eval_rows, now_ms):
                    # Candidate strikes for this signal's direction — the SAME picks
''',
'''                ordered = sorted(moneyness, key=lambda m: _MONEYNESS_ORDER.get(m, 99))
                latest_ts = candles[-1].timestamp_ms

                # Confluence must exist on one bar; never join an old underlying
                # trigger to a premium trend observed later.
                for row in eval_rows:
                    if not row.is_fresh or int(row.timestamp_ms) != int(latest_ts):
                        continue
                    # Candidate strikes for this signal's direction — the SAME picks
''')

replace_once(SCANNER,
'''                        if len(oc) <= 1:
                            continue
                        diag.deriv_charts += 1
                        bars = len(oc)
''',
'''                        if len(oc) <= 1:
                            continue
                        if int(oc[-1].timestamp_ms) != int(latest_ts):
                            continue
                        diag.deriv_charts += 1
                        bars = len(oc)
''')

replace_once(SCANNER,
'''                        leg.premium_spot = float(oc[-1].close)
                        leg.premium_sl = d.stop_loss
                        leg.entry_sl = d.entry_sl
                        leg.token = pick.token
                        leg.is_active = d.is_active
                        confirmed.append(leg)
''',
'''                        leg.premium_spot = float(oc[-1].close)
                        leg.premium_sl = d.stop_loss
                        # This trade starts on the confluence bar, so do not inherit
                        # the static stop from an older standalone premium entry.
                        leg.entry_sl = d.stop_loss
                        leg.token = pick.token
                        leg.is_active = d.is_active
                        leg.entry_timestamp_ms = int(row.timestamp_ms)
                        confirmed.append(leg)
''')

replace_once(SERVICE,
'''            leg = min(row.legs, key=lambda l: abs(l.strike - row.spot)) if row.legs else None
            if leg is not None:
''',
'''            # Reuse the exact leg selected by option_order_args. Independently
            # resolving against grouped row.spot (zero) could select another strike.
            leg = next((l for l in row.legs if l.option_symbol == trade_symbol), None)
            if leg is None and row.legs:
                reference_spot = float(row.underlying_spot or row.spot or 0.0)
                leg = min(row.legs, key=lambda l: abs(l.strike - reference_spot))
            if leg is not None:
''')

# Apply the frontend and regression patches in this same process chain. The old
# workflow stops on the first non-zero script; committing the generated source
# here makes the exact tree inspectable even when a later validation fails.
env = dict(os.environ, STERLING_PATCH_RECOVERY='1')
for script in ('patch_frontend.py', 'patch_tests.py'):
    proc = subprocess.run([sys.executable, f'.github/signal-integrity/{script}'],
                          text=True, capture_output=True, env=env)
    if proc.returncode:
        errors.append(f'{script}:\n{proc.stdout}\n{proc.stderr}')

Path('.github/signal-integrity/recovery.log').write_text('\n\n'.join(errors) or 'all patch anchors applied')
subprocess.run(['git', 'config', 'user.name', 'OpenAI'])
subprocess.run(['git', 'config', 'user.email', 'noreply@openai.com'])
subprocess.run(['git', 'add', 'backend', 'frontend', '.github/signal-integrity/recovery.log'])
if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode != 0:
    subprocess.run(['git', 'commit', '-m', 'fix(kite): apply signal-integrity source for verification'], check=False)
    subprocess.run(['git', 'push', 'origin', 'HEAD:fix/kite-signal-integrity-audit'], check=False)

if errors:
    raise RuntimeError('\n\n'.join(errors))
print('backend, frontend, and tests patches applied and persisted')
