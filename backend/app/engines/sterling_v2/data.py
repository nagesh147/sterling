from __future__ import annotations
import glob, os
import pandas as pd
from app.engines.edge.strategies import resample as _edge_resample

_PARQUET_GLOB = "vector_store_1m_*.parquet"


def parquet_dir() -> str:
    # backend/ — parquets live alongside the app package.
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))


def list_symbols() -> dict[str, str]:
    base = parquet_dir()
    out = {}
    for f in sorted(glob.glob(os.path.join(base, _PARQUET_GLOB))):
        sym = os.path.basename(f).split("_")[-1].replace(".parquet", "")
        out[sym] = f
    return out


def load_symbol(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.set_index("time").sort_index()


def resample_tf(df_1m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Reuse the edge resampler (recomputes ATR(14) on the new bars)."""
    return _edge_resample(df_1m, rule)
