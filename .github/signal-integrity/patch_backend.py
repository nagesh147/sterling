from pathlib import Path


def replace(path, old, new):
    p = Path(path)
    text = p.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f'{path}: expected one match, got {text.count(old)}')
    p.write_text(text.replace(old, new, 1))


replace(
    'backend/app/engines/sterling_kite_engine/schemas.py',
    '''    token: Optional[int] = None
    is_active: bool = False   # this contract's SuperTrend is still aligned on the latest bar
''',
    '''    token: Optional[int] = None
    is_active: bool = False   # this contract's SuperTrend is still aligned on the latest bar
    # Per-contract provenance. Grouped derivative rows must not borrow another
    # strike's timestamp/alignment/exit state from their shared parent row.
    signal_timestamp_ms: Optional[int] = None
    entry_timestamp_ms: Optional[int] = None
    alignment: Optional[AlignmentChip] = None
    exit_state: Optional[str] = None
''',
)

replace(
    'backend/app/services/kite_engine/scanner.py',
    '''        leg.premium_spot = r.spot
        leg.premium_sl = r.stop_loss
        leg.token = r.token
        sym_key = (*key, leg.option_symbol)
''',
    '''        leg.premium_spot = r.spot
        leg.premium_sl = r.stop_loss
        leg.token = r.token
        # Keep the selected contract's own evidence. The grouped row timestamp is
        # only a summary and must never be reused as the leg's chart entry time.
        leg.signal_timestamp_ms = int(leg.signal_timestamp_ms or r.timestamp_ms)
        leg.entry_timestamp_ms = int(leg.entry_timestamp_ms or r.timestamp_ms)
        leg.alignment = leg.alignment or r.alignment
        leg.exit_state = leg.exit_state or r.exit_state
        sym_key = (*key, leg.option_symbol)
''',
)

replace(
    'backend/app/services/kite_engine/scanner.py',
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
''',
)

replace(
    'backend/app/services/kite_engine/scanner.py',
    '''        OptionLeg(moneyness=m, option_type=p.option_type, option_symbol=p.option_symbol,
                  strike=p.strike, expiry=p.expiry, lot_size=p.lot_size or None)
''',
    '''        OptionLeg(moneyness=m, option_type=p.option_type, option_symbol=p.option_symbol,
                  strike=p.strike, expiry=p.expiry, lot_size=p.lot_size or None,
                  entry_timestamp_ms=row.timestamp_ms)
''',
)

replace(
    'backend/app/services/kite_engine/scanner.py',
    '''    if leg is None and row.legs:
        leg = min(row.legs, key=lambda l: abs(l.strike - row.spot))
    if leg is None:
        return None
    return {
''',
    '''    if leg is None and row.legs:
        # Grouped derivative rows zero row.spot; select ATM against underlying_spot,
        # not against zero (which previously picked the lowest strike).
        reference_spot = float(row.underlying_spot or row.spot or 0.0)
        leg = min(row.legs, key=lambda l: abs(l.strike - reference_spot))
    if leg is None:
        return None
    return {
''',
)

replace(
    'backend/app/services/kite_engine/scanner.py',
    '''        "stop_loss": float(row.stop_loss),
''',
    '''        "stop_loss": float(leg.premium_sl or row.stop_loss),
''',
)

replace(
    'backend/app/services/kite_engine/scanner.py',
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
                        int(x.timestamp_ms),
                    }
                    for l in x.legs
                )
            if not _matches(r):
                return next((x for x in self.rows if _matches(x)), None)
        return r
''',
)

replace(
    'backend/app/services/kite_engine/scanner.py',
    '''                for row in _retain_signals(eval_rows, now_ms):
                    # Candidate strikes for this signal's direction — the SAME picks
''',
    '''                for row in eval_rows:
                    # Confluence is a same-bar event. Joining an old underlying entry
                    # to a premium that is green today fabricates a signal that never
                    # existed at one point in time.
                    if not row.is_fresh or int(row.timestamp_ms) != int(latest_ts):
                        continue
                    # Candidate strikes for this signal's direction — the SAME picks
''',
)

replace(
    'backend/app/services/kite_engine/scanner.py',
    '''                        if len(oc) <= 1:
                            continue
                        diag.deriv_charts += 1
''',
    '''                        if len(oc) <= 1:
                            continue
                        # Never confirm a fresh underlying bar using a stale premium feed.
                        if int(oc[-1].timestamp_ms) != int(latest_ts):
                            continue
                        diag.deriv_charts += 1
''',
)

replace(
    'backend/app/services/kite_engine/scanner.py',
    '''                        leg.premium_spot = float(oc[-1].close)
                        leg.premium_sl = d.stop_loss
                        leg.entry_sl = d.entry_sl
                        leg.token = pick.token
                        leg.is_active = d.is_active
                        confirmed.append(leg)
''',
    '''                        leg.premium_spot = float(oc[-1].close)
                        leg.premium_sl = d.stop_loss
                        # Confluence enters now; its initial stop is the current premium
                        # trail, not the premium's potentially older standalone entry stop.
                        leg.entry_sl = d.stop_loss
                        leg.token = pick.token
                        leg.is_active = d.is_active
                        leg.entry_timestamp_ms = int(row.timestamp_ms)
                        # signal_timestamp/alignment/exit_state stay premium-specific.
                        confirmed.append(leg)
''',
)

print('backend signal-integrity patch applied')
