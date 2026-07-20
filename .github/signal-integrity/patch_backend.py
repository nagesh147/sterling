from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


SCHEMAS = 'backend/app/engines/sterling_kite_engine/schemas.py'
SCANNER = 'backend/app/services/kite_engine/scanner.py'
SERVICE = 'backend/app/services/kite_engine/service.py'

replace_once(
    SCHEMAS,
    '''    token: Optional[int] = None
    is_active: bool = False   # this contract's SuperTrend is still aligned on the latest bar
''',
    '''    token: Optional[int] = None
    is_active: bool = False   # this contract's SuperTrend is still aligned on the latest bar
    # Contract-local evidence. A grouped derivative parent is only a display/sort
    # summary; opening or executing one strike must use that strike's own values.
    signal_timestamp_ms: Optional[int] = None
    entry_timestamp_ms: Optional[int] = None
    alignment: Optional[AlignmentChip] = None
    exit_state: Optional[str] = None
''',
)

replace_once(
    SCANNER,
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
''',
)

replace_once(
    SCANNER,
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

replace_once(
    SCANNER,
    '''        OptionLeg(moneyness=m, option_type=p.option_type, option_symbol=p.option_symbol,
                  strike=p.strike, expiry=p.expiry, lot_size=p.lot_size or None)
''',
    '''        OptionLeg(moneyness=m, option_type=p.option_type, option_symbol=p.option_symbol,
                  strike=p.strike, expiry=p.expiry, lot_size=p.lot_size or None,
                  entry_timestamp_ms=row.timestamp_ms)
''',
)

replace_once(
    SCANNER,
    '''    if leg is None and row.legs:
        leg = min(row.legs, key=lambda l: abs(l.strike - row.spot))
    if leg is None:
        return None
    return {
''',
    '''    if leg is None and row.legs:
        # Grouped derivative rows intentionally zero row.spot. Resolve ATM against
        # the underlying spot, never against zero (which selected the lowest strike).
        reference_spot = float(row.underlying_spot or row.spot or 0.0)
        leg = min(row.legs, key=lambda l: abs(l.strike - reference_spot))
    if leg is None:
        return None
    return {
''',
)

replace_once(
    SCANNER,
    '''        "stop_loss": float(row.stop_loss),
''',
    '''        "stop_loss": float(leg.premium_sl if leg.premium_sl is not None else row.stop_loss),
''',
)

replace_once(
    SCANNER,
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
''',
)

replace_once(
    SCANNER,
    '''                ordered = sorted(moneyness, key=lambda m: _MONEYNESS_ORDER.get(m, 99))
                latest_ts = candles[-1].timestamp_ms

                for row in _retain_signals(eval_rows, now_ms):
                    # Candidate strikes for this signal's direction — the SAME picks
''',
    '''                ordered = sorted(moneyness, key=lambda m: _MONEYNESS_ORDER.get(m, 99))
                latest_ts = candles[-1].timestamp_ms

                # Confluence is an event, not a retrospective join. Only a fresh
                # underlying transition on the latest closed bar may start a trade.
                for row in eval_rows:
                    if not row.is_fresh or int(row.timestamp_ms) != int(latest_ts):
                        continue
                    # Candidate strikes for this signal's direction — the SAME picks
''',
)

replace_once(
    SCANNER,
    '''                        if len(oc) <= 1:
                            continue
                        diag.deriv_charts += 1
                        bars = len(oc)
''',
    '''                        if len(oc) <= 1:
                            continue
                        # Do not confirm today's underlying signal with a stale option
                        # feed. Both legs must refer to the same latest closed 1H bar.
                        if int(oc[-1].timestamp_ms) != int(latest_ts):
                            continue
                        diag.deriv_charts += 1
                        bars = len(oc)
''',
)

replace_once(
    SCANNER,
    '''                        leg.premium_spot = float(oc[-1].close)
                        leg.premium_sl = d.stop_loss
                        leg.entry_sl = d.entry_sl
                        leg.token = pick.token
                        leg.is_active = d.is_active
                        confirmed.append(leg)
''',
    '''                        leg.premium_spot = float(oc[-1].close)
                        leg.premium_sl = d.stop_loss
                        # The confluence position starts now. Its static initial stop
                        # must be rebased to the current premium trail, not an older
                        # standalone premium-entry candle.
                        leg.entry_sl = d.stop_loss
                        leg.token = pick.token
                        leg.is_active = d.is_active
                        leg.entry_timestamp_ms = int(row.timestamp_ms)
                        confirmed.append(leg)
''',
)

replace_once(
    SERVICE,
    '''            leg = min(row.legs, key=lambda l: abs(l.strike - row.spot)) if row.legs else None
            if leg is not None:
''',
    '''            # Keep execution metadata aligned with the exact contract selected
            # by option_order_args. Grouped derivative parents have row.spot == 0,
            # so independently choosing nearest-to-row.spot could pick another strike.
            leg = next((l for l in row.legs if l.option_symbol == trade_symbol), None)
            if leg is None and row.legs:
                reference_spot = float(row.underlying_spot or row.spot or 0.0)
                leg = min(row.legs, key=lambda l: abs(l.strike - reference_spot))
            if leg is not None:
''',
)

# Fail closed: the workflow must never report success after silently skipping a
# critical mutation.
assert 'signal_timestamp_ms: Optional[int] = None' in Path(SCHEMAS).read_text()
scanner = Path(SCANNER).read_text()
for required in (
    'leg.signal_timestamp_ms = int(leg.signal_timestamp_ms or r.timestamp_ms)',
    'reference_spot = float(row.underlying_spot or row.spot or 0.0)',
    'leg.premium_sl if leg.premium_sl is not None else row.stop_loss',
    'if not row.is_fresh or int(row.timestamp_ms) != int(latest_ts):',
    'if int(oc[-1].timestamp_ms) != int(latest_ts):',
    'leg.entry_timestamp_ms = int(row.timestamp_ms)',
):
    assert required in scanner, required
assert 'l.option_symbol == trade_symbol' in Path(SERVICE).read_text()
print('backend signal-integrity patch applied')
