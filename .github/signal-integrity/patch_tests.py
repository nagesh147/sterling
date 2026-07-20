from pathlib import Path

# Trigger the pull-request workflow after its checkout target was corrected.


def replace(path, old, new):
    p = Path(path)
    text = p.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f'{path}: expected one match, got {text.count(old)}')
    p.write_text(text.replace(old, new, 1))


replace(
    'backend/tests/engines/sterling_kite_engine/test_scanner.py',
    '''    _SIGNAL_RETENTION_MS, KiteEngineScanner, _retain_signals, attach_strikes,
    drop_forming, evaluate_derivative_contract, evaluate_item, option_order_args,
''',
    '''    _SIGNAL_RETENTION_MS, KiteEngineScanner, _compile_rows, _retain_signals, attach_strikes,
    drop_forming, evaluate_derivative_contract, evaluate_item, option_order_args,
''',
)

p = Path('backend/tests/engines/sterling_kite_engine/test_scanner.py')
text = p.read_text()
text += r'''

# ── signal provenance / CE+PE premium semantics regressions ──────────────────
@pytest.mark.parametrize(
    ("option_type", "expected_regime", "symbol"),
    [
        ("CE", "BULL", "HDFCBANK26JUL825CE"),
        ("PE", "BEAR", "HDFCBANK26JUL825PE"),
    ],
)
def test_derivative_option_is_long_premium_and_stamps_three_green_leg_provenance(
    option_type, expected_regime, symbol,
):
    """Both CE and PE derivative entries BUY a rising option premium.

    CE/PE only changes the underlying view (BULL/BEAR); it must never change the
    premium entry requirement from a fresh three-green alignment to three-red.
    """
    cfg = SterlingKiteEngineConfig()
    item = UniverseItem("HDFCBANK", "HDFCBANK", 1, "NSE", "NFO")
    pick = OptionPick(option_symbol=symbol, strike=825.0, option_type=option_type,
                      expiry="2026-07-30", dte=9, lot_size=550, token=12345)
    candles = _trim_to_transition(_candles(_fresh_long_path()), cfg, "long")
    row = evaluate_derivative_contract(item, "ITM3", pick, candles, cfg)[-1]
    leg = row.legs[0]
    assert row.regime == expected_regime
    assert row.direction == "long"
    assert (leg.alignment.fast, leg.alignment.mid, leg.alignment.slow) == (1, 1, 1)
    assert leg.signal_timestamp_ms == row.timestamp_ms
    assert leg.entry_timestamp_ms == row.timestamp_ms
    assert leg.exit_state == row.exit_state


def test_grouped_derivative_rows_preserve_each_leg_timestamp_and_exit_state():
    from app.engines.sterling_kite_engine.schemas import AlignmentChip, EngineSignalRow, OptionLeg

    def make_row(symbol, token, ts, exit_state):
        alignment = AlignmentChip(fast=1, mid=1, slow=1)
        return EngineSignalRow(
            underlying="HDFCBANK", token=token, exchange="NFO", regime="BEAR",
            alignment=alignment, direction="long", option_type="PE",
            legs=[OptionLeg(moneyness="ITM3", option_type="PE", option_symbol=symbol,
                            strike=825.0 + token, expiry="2026-07-30", token=token,
                            is_active=True, signal_timestamp_ms=ts,
                            entry_timestamp_ms=ts, alignment=alignment, exit_state=exit_state)],
            spot=40.0 + token, stop_loss=30.0 + token, score=85.0,
            timestamp_ms=ts, source="derivatives", is_active=True,
        )

    grouped = _compile_rows([
        make_row("HDFCBANK_A_PE", 1, 1000, "0/3 red"),
        make_row("HDFCBANK_B_PE", 2, 2000, "1/3 red"),
    ])
    assert len(grouped) == 1
    by_symbol = {leg.option_symbol: leg for leg in grouped[0].legs}
    assert by_symbol["HDFCBANK_A_PE"].entry_timestamp_ms == 1000
    assert by_symbol["HDFCBANK_A_PE"].exit_state == "0/3 red"
    assert by_symbol["HDFCBANK_B_PE"].entry_timestamp_ms == 2000
    assert by_symbol["HDFCBANK_B_PE"].exit_state == "1/3 red"


def test_option_order_args_grouped_derivative_uses_underlying_spot_and_leg_stop():
    from app.engines.sterling_kite_engine.schemas import AlignmentChip, EngineSignalRow, OptionLeg

    row = EngineSignalRow(
        underlying="HDFCBANK", token=1, exchange="NFO", regime="BEAR",
        alignment=AlignmentChip(fast=1, mid=1, slow=1), direction="long", option_type="PE",
        legs=[
            OptionLeg(moneyness="ITM3", option_type="PE", option_symbol="LOW",
                      strike=800, expiry="2026-07-30", lot_size=550,
                      premium_spot=45, premium_sl=31),
            OptionLeg(moneyness="ATM", option_type="PE", option_symbol="ATM",
                      strike=825, expiry="2026-07-30", lot_size=550,
                      premium_spot=30, premium_sl=22),
        ],
        spot=0, underlying_spot=824, stop_loss=0, score=85, timestamp_ms=1,
        source="derivatives",
    )
    args = option_order_args(row)
    assert args["option_symbol"] == "ATM"
    assert args["stop_loss"] == 22
    assert args["stop_premium"] == 22
'''
p.write_text(text)

Path('frontend/src/components/charts/signalMarkerLogic.test.ts').write_text('''import { describe, expect, it } from 'vitest';
import { freshTripleAlignmentIndex, nearestCandleIndex } from './signalMarkerLogic';

const p = (direction: 'up' | 'down') => ({ direction });

describe('signal marker integrity', () => {
  it.each(['CE', 'PE'])('never substitutes a nearby three-red transition for a %s long-premium entry', () => {
    const times = [100, 200, 300, 400];
    const fast = [p('up'), p('down'), p('down'), p('up')];
    const mid = [p('up'), p('down'), p('down'), p('up')];
    const slow = [p('up'), p('down'), p('down'), p('up')];
    expect(freshTripleAlignmentIndex(fast, mid, slow, times, 200, 'up', 150)).toBe(-1);
    expect(freshTripleAlignmentIndex(fast, mid, slow, times, 200, 'down', 150)).toBe(1);
  });

  it.each(['CE', 'PE'])('finds the intended fresh three-green %s premium transition', () => {
    const times = [100, 200, 300];
    const fast = [p('down'), p('up'), p('up')];
    const mid = [p('down'), p('up'), p('up')];
    const slow = [p('down'), p('up'), p('up')];
    expect(freshTripleAlignmentIndex(fast, mid, slow, times, 205, 'up', 20)).toBe(1);
  });

  it('only returns a time fallback inside tolerance', () => {
    expect(nearestCandleIndex([100, 200, 300], 205, 10)).toBe(1);
    expect(nearestCandleIndex([100, 200, 300], 500, 10)).toBe(-1);
  });
});
''')

print('signal-integrity tests added')
