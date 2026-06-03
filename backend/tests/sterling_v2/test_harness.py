import numpy as np
import pandas as pd
import pytest
from app.engines.sterling_v2 import data as v2data


def test_list_symbols_finds_parquets():
    syms = v2data.list_symbols()
    assert set(syms).issuperset({"BTCUSD"})  # BTC parquet must exist


def test_resample_4h_has_atr():
    syms = v2data.list_symbols()
    df = v2data.load_symbol(syms["BTCUSD"])
    d4 = v2data.resample_tf(df, "4h")
    assert "atr" in d4.columns and len(d4) > 1000
