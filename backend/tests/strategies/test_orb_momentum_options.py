from datetime import datetime, timedelta
from app.engines.orb_momentum_options import ORBMomentumConfig, UnderlyingBar, OptionCandidate, generate_signal, select_option
from app.services.orb_momentum_scanner import ORBMomentumScanner


def bars(symbol_seed=0):
    out=[]
    price=100.0
    for i in range(80):
        t=datetime(2026,8,18,9,15)+timedelta(minutes=5*i)
        out.append(UnderlyingBar(t,price,price+1,price-1,price,1000))
        price += 0.02
    # Force a clean upside breakout in the latest bar.
    last=out[-1]; out[-1]=UnderlyingBar(last.timestamp,last.open,106,100,105,5000)
    return out


def test_strategy_is_independent_and_generates_long_signal():
    cfg=ORBMomentumConfig()
    signal=generate_signal("TEST",bars(),cfg)
    assert signal.direction == "LONG"
    assert signal.reason.startswith("opening-range")


def test_option_selection_maps_long_to_ce():
    contracts=[OptionCandidate("TESTCE", "CE", 105, "2026-08-27", 10, 9.9, 10.1, 75)]
    selected=select_option(105,"LONG",contracts,ORBMMomentumConfig if False else ORBMomentumConfig())
    assert selected is not None and selected.option_type == "CE"


def test_scanner_publishes_strategy_owned_signal():
    contracts=[OptionCandidate("TESTCE", "CE", 105, "2026-08-27", 10, 9.9, 10.1, 75)]
    scanner=ORBMomentumScanner()
    result=scanner.evaluate("TEST",bars(),contracts)
    assert result is not None
    assert result["strategy"] == "ORB_MOMENTUM_OPTIONS"
    assert result["status"] == "SIGNAL"
    assert scanner.signals()[0]["underlying"] == "TEST"
