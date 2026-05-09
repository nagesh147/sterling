import pytest
from app.engines.directional.structure_selector import select_leverage


def test_max_score_strong_signal_gives_50x():
    """score=100 + STRONG → 50x leverage."""
    assert select_leverage(100.0, "STRONG") == 50


def test_score_92_strong_gives_25x():
    assert select_leverage(92.0, "STRONG") == 25


def test_score_85_strong_gives_10x():
    assert select_leverage(85.0, "STRONG") == 10


def test_never_returns_200x():
    """200x is removed — max is 50x."""
    for score in [50, 75, 85, 90, 95, 100]:
        lev = select_leverage(float(score), "STRONG")
        assert lev <= 50, f"Leverage {lev} for score {score} exceeds 50x cap"


def test_high_score_non_strong_capped_at_5x():
    """score >= 85 but signal != STRONG → cap at 5x for high leverage tiers."""
    lev = select_leverage(90.0, "SIGNAL")
    assert lev <= 5


def test_score_80_gives_5x():
    assert select_leverage(80.0, "SIGNAL") == 5


def test_score_75_gives_3x():
    assert select_leverage(75.0, "SIGNAL") == 3


def test_score_below_75_gives_1x():
    assert select_leverage(60.0, "NONE") == 1
