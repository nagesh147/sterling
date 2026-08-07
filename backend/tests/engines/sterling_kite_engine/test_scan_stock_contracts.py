"""`scan_stock_contracts` — the master switch above the stock list.

Single-stock derivatives list a monthly cycle only, settle physically at expiry,
and are the bulk of the scan cost, so "indices only" deserves to be one click
rather than un-ticking every name.

The switch works by dropping single-stock items in `select_scan_universe`, the
one place both engines resolve their universe — so nothing downstream ever sees
a stock, and no half-resolved stock row can appear.
"""
from app.engines.sterling_kite_engine.schemas import EngineConfigModel
from app.services.kite_engine.universe import UniverseItem, select_scan_universe


def _item(name, *, is_index):
    return UniverseItem(
        name=name, tradingsymbol=name, token=1, exchange="NSE",
        option_exchange="NFO", is_index=is_index,
    )


def _universe():
    return [
        _item("NIFTY 50", is_index=True),
        _item("NIFTY BANK", is_index=True),
        _item("RELIANCE", is_index=False),
        _item("TCS", is_index=False),
    ]


def test_defaults_to_scanning_stock_contracts():
    """An existing config must scan exactly what it scanned before."""
    assert EngineConfigModel().scan_stock_contracts is True


def test_off_drops_every_stock_but_keeps_indices():
    selected = select_scan_universe(
        _universe(), indices=["NIFTY 50", "NIFTY BANK"],
        stocks=["RELIANCE", "TCS"], all_stocks=False, stock_contracts=False,
    )
    assert [i.name for i in selected] == ["NIFTY 50", "NIFTY BANK"]


def test_off_overrides_all_stocks():
    """It is a master switch, not another entry in the list."""
    selected = select_scan_universe(
        _universe(), indices=["NIFTY 50"],
        stocks=[], all_stocks=True, stock_contracts=False,
    )
    assert [i.name for i in selected] == ["NIFTY 50"]


def test_on_preserves_the_existing_selection():
    selected = select_scan_universe(
        _universe(), indices=["NIFTY 50"],
        stocks=["RELIANCE"], all_stocks=False, stock_contracts=True,
    )
    assert [i.name for i in selected] == ["NIFTY 50", "RELIANCE"]


def test_omitting_the_argument_keeps_the_old_behaviour():
    """Every existing call site passes nothing and must be unaffected."""
    with_default = select_scan_universe(
        _universe(), indices=["NIFTY 50"], stocks=["RELIANCE"], all_stocks=False)
    explicit_on = select_scan_universe(
        _universe(), indices=["NIFTY 50"], stocks=["RELIANCE"],
        all_stocks=False, stock_contracts=True)
    assert [i.name for i in with_default] == [i.name for i in explicit_on]


def test_turning_it_off_does_not_clear_the_stock_selection():
    """The list is kept so ticking it back on restores the previous universe."""
    cfg = EngineConfigModel(scan_stocks=["RELIANCE"], scan_stock_contracts=False)
    assert cfg.scan_stocks == ["RELIANCE"]

    restored = select_scan_universe(
        _universe(), indices=["NIFTY 50"], stocks=cfg.scan_stocks,
        all_stocks=False, stock_contracts=True,
    )
    assert [i.name for i in restored] == ["NIFTY 50", "RELIANCE"]
