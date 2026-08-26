from app.engines.nifty_orb_options import StrategyConfig
from app.services.nifty_orb_scanner import configured_underlyings


def test_configured_universe_deduplicates_indices_and_stocks():
    cfg=StrategyConfig(scan_indices=('NIFTY','NIFTY 50','BANKNIFTY'),scan_stocks=('SBIN','INFY'),scan_stock_contracts=True)
    assert configured_underlyings(cfg)==['NIFTY','BANKNIFTY','SBIN','INFY']


def test_fallback_underlying_is_used_when_universe_is_empty():
    cfg=StrategyConfig(underlying='SBIN',scan_indices=(),scan_stocks=(),scan_stock_contracts=False)
    assert configured_underlyings(cfg)==['SBIN']
