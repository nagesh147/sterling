from pathlib import Path

path = Path('backend/tests/engines/sterling_kite_engine/test_scanner.py')
text = path.read_text()

old = '''    cfg = SterlingKiteEngineConfig()
    fired = _trim_to_transition(_candles(_fresh_long_path()), cfg, "long")

    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            if inst.zerodha_token == 100:      # the underlying fires long
                return fired
            return _candles(_fresh_long_path())  # whichever option is picked, its premium confirms
'''
new = '''    cfg = SterlingKiteEngineConfig()
    fired = _trim_to_transition(_candles(_fresh_long_path()), cfg, "long")
    # Same closed bar on both feeds: no retrospective/future-bar confluence.
    premium = _trim_to_transition(_candles(_fresh_long_path()), cfg, "long")

    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            if inst.zerodha_token == 100:      # the underlying fires long
                return fired
            return premium  # selected option confirms on the same closed bar
'''
if new not in text:
    if text.count(old) != 1:
        raise RuntimeError(f'first confluence fixture anchor count={text.count(old)}')
    text = text.replace(old, new, 1)

old = '''    # Option premium climbs 150→600 through the up-leg; its ST long fires mid-climb and
    # stays running to the last bar, so the entry-bar premium is far below the last close.
    premium = _candles(_fresh_long_path())

    class FakeClient:
'''
new = '''    # Option premium climbs 150→600 and became bullish earlier, but its latest
    # closed candle is timestamp-aligned with the fresh underlying trigger. Shifting
    # timestamps preserves the price path while preventing a future-bar lookahead.
    premium = _candles(_fresh_long_path())
    shift_ms = fired[-1].timestamp_ms - premium[-1].timestamp_ms
    for candle in premium:
        candle.timestamp_ms += shift_ms

    class FakeClient:
'''
if new not in text:
    if text.count(old) != 1:
        raise RuntimeError(f'second confluence fixture anchor count={text.count(old)}')
    text = text.replace(old, new, 1)

path.write_text(text)
print('signal-integrity regressions aligned to same-bar confluence semantics')
