from pathlib import Path

required = {
    'backend/app/engines/sterling_kite_engine/schemas.py': [
        'signal_timestamp_ms: Optional[int] = None',
        'entry_timestamp_ms: Optional[int] = None',
        'alignment: Optional[AlignmentChip] = None',
        'exit_state: Optional[str] = None',
    ],
    'backend/app/services/kite_engine/scanner.py': [
        'leg.signal_timestamp_ms = int(leg.signal_timestamp_ms or r.timestamp_ms)',
        'signal_timestamp_ms=ts, entry_timestamp_ms=ts',
        'reference_spot = float(row.underlying_spot or row.spot or 0.0)',
        'leg.premium_sl if leg.premium_sl is not None else row.stop_loss',
        'if not row.is_fresh or int(row.timestamp_ms) != int(latest_ts):',
        'if int(oc[-1].timestamp_ms) != int(latest_ts):',
        'leg.entry_timestamp_ms = int(row.timestamp_ms)',
    ],
    'backend/app/services/kite_engine/service.py': [
        'l.option_symbol == trade_symbol',
        'reference_spot = float(row.underlying_spot or row.spot or 0.0)',
    ],
}

missing = []
for path, needles in required.items():
    text = Path(path).read_text()
    for needle in needles:
        if needle not in text:
            missing.append(f'{path}: {needle}')
if missing:
    raise RuntimeError('backend signal-integrity source incomplete:\n' + '\n'.join(missing))
print('backend signal-integrity source verified')
