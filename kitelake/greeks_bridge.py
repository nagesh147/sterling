"""The one place kitelake reaches into the Sterling backend, and why.

Sterling already has a correct, stdlib-only Black-Scholes implementation at
``backend/app/services/kite_engine/greeks.py`` — ``implied_vol`` (Newton-Raphson from a
Brenner-Subrahmanyam seed with a bisection fallback), ``black_scholes_greeks`` and
``bs_price``. A second pricing model in this package would be the worst possible outcome:
two implementations that agree today, disagree after one edit, and leave nobody sure which
number a position was sized against.

So the dependency is deliberate, and confined to this module. Everything else in kitelake
stays standalone. The import is tried three ways because kitelake runs in two different
contexts — inside the backend process (where ``app`` is already importable) and from the
standalone CLI (where it is not).

Note the units, which are the backend's and are not the textbook ones:
``iv`` is a decimal (0.18 = 18%), ``dte_days`` is calendar days, ``theta`` is per calendar
day, and ``vega`` is per 1% vol move.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

__all__ = ["greeks_available", "black_scholes_greeks", "implied_vol", "bs_price", "RISK_FREE"]

#: India ~risk-free, matching the backend's ``_R_DEFAULT``. Re-exported so callers can see
#: the assumption rather than discovering it inside the model.
RISK_FREE = 0.065

_REPO_ROOT = Path(__file__).resolve().parent.parent


class GreeksUnavailable(RuntimeError):
    """The backend pricing module could not be imported."""


#: The pricing source of truth. Loaded by path, not by package import — see _module().
_GREEKS_FILE = _REPO_ROOT / "backend" / "app" / "services" / "kite_engine" / "greeks.py"


@lru_cache(maxsize=1)
def _module() -> Any:
    """Get the backend greeks module, preferring a normal import, else loading the file.

    The normal import only works inside the backend process. Standalone — the CLI, the tick
    pipe — it fails, and not because greeks.py needs anything: importing
    ``app.services.kite_engine.greeks`` first executes that package's ``__init__``, which
    pulls in ``expiry_series_runtime`` and thence pydantic, absent from kitelake's venv.

    So the fallback loads greeks.py directly by path. That is sound precisely because the
    file is stdlib-only (``math`` and ``dataclasses``) — it has no intra-backend imports to
    satisfy. It is still the same source file, so there is exactly one pricing model in the
    repo; only the route to it differs.
    """
    if "app.services.kite_engine.greeks" in sys.modules:
        return sys.modules["app.services.kite_engine.greeks"]
    try:
        from app.services.kite_engine import greeks as mod  # noqa: PLC0415

        return mod
    except Exception:
        pass  # expected outside the backend process; fall through to loading the file

    import importlib.util

    if not _GREEKS_FILE.exists():
        raise GreeksUnavailable(
            f"Sterling's option pricing module is missing: {_GREEKS_FILE}\n"
            "The tick pipeline needs it for IV and greeks."
        )
    try:
        spec = importlib.util.spec_from_file_location("kitelake._vendored_greeks", _GREEKS_FILE)
        if spec is None or spec.loader is None:
            raise ImportError("could not build a module spec")
        mod = importlib.util.module_from_spec(spec)
        # Register BEFORE executing. @dataclass resolves annotations via
        # sys.modules[cls.__module__]; with the module absent that lookup returns None and
        # the decorator dies with a bare AttributeError inside dataclasses.
        sys.modules[spec.name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            sys.modules.pop(spec.name, None)
            raise
    except Exception as exc:
        raise GreeksUnavailable(
            f"Could not load {_GREEKS_FILE}: {type(exc).__name__}: {exc}"
        ) from exc
    for required in ("implied_vol", "black_scholes_greeks", "bs_price"):
        if not hasattr(mod, required):
            raise GreeksUnavailable(
                f"{_GREEKS_FILE} no longer defines {required}() — the pricing contract moved."
            )
    return mod


def greeks_available() -> bool:
    """True when pricing can be done. Never raises, so callers can degrade gracefully."""
    try:
        _module()
        return True
    except GreeksUnavailable:
        return False


def implied_vol(
    *, price: float, spot: float, strike: float, dte_days: float, option_type: str,
    rate: float = RISK_FREE,
) -> float:
    """Back IV out of a market premium. Returns 0.0 when unsolvable (e.g. below intrinsic)."""
    return _module().implied_vol(
        price=price, spot=spot, strike=strike, dte_days=dte_days,
        option_type=option_type, rate=rate,
    )


def black_scholes_greeks(
    *, spot: float, strike: float, dte_days: float, iv: float, option_type: str,
    rate: float = RISK_FREE,
) -> Any:
    """Greeks dataclass with ``delta, gamma, theta, vega, solved``.

    ``solved=False`` means the model could not be evaluated and only the intrinsic sign of
    delta is meaningful — the backend added that flag precisely because a "no data" answer
    is otherwise shaped exactly like a very confident one.
    """
    return _module().black_scholes_greeks(
        spot=spot, strike=strike, dte_days=dte_days, iv=iv,
        option_type=option_type, rate=rate,
    )


def bs_price(
    *, spot: float, strike: float, dte_days: float, iv: float, option_type: str,
    rate: float = RISK_FREE,
) -> float:
    return _module().bs_price(
        spot=spot, strike=strike, dte_days=dte_days, iv=iv,
        option_type=option_type, rate=rate,
    )
