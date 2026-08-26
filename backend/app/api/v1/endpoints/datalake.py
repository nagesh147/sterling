"""Data-lake endpoints — ``/api/v1/datalake/*``.

Surfaces the ``kitelake`` offline market-data lake to the UI, including the folder picker
that lets a user say where the data lives.

**The central design rule: an unavailable lake is a 200, not a 500.** The data normally sits
on a removable drive, so "not plugged in" is an ordinary, expected state. Returning an error
status would make the frontend paint a red failure banner for something the user simply
needs to be told about. Every endpoint here therefore answers with
``{"available": false, "reason": ..., "guidance": [...]}`` and lets the UI render help.

Genuine 4xx/5xx are reserved for real faults: a malformed request, or a path the user chose
that cannot be written.

**Every handler here is a plain ``def``, not ``async def``, and must stay that way.** They
all do blocking work — SQLite on the manifest, parquet reads, directory scans — and none of
them await anything. FastAPI runs ``async def`` handlers *on the event loop*, so a slow read
from the removable drive blocks the whole process: during one such stall even ``/health``
timed out, taking the live trading routes down with it. Declared as ``def``, FastAPI runs
them in its threadpool, where blocking is exactly what you want.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import UserContext, get_current_user
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/datalake", tags=["datalake"])

#: ``kitelake`` lives at the repository root, beside ``backend/``. The backend is usually
#: started from inside ``backend/``, so the root is not on sys.path by default.
_REPO_ROOT = Path(__file__).resolve().parents[5]


def _kitelake() -> Any:
    """Import the kitelake package, adding the repo root to sys.path if needed.

    Raises:
        RuntimeError: with an actionable message if the package or its deps are missing.
            Callers convert this into an ``available: false`` payload rather than a 500.
    """
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    try:
        import kitelake  # noqa: PLC0415

        return kitelake
    except Exception as exc:  # ImportError, or a missing pyarrow/polars/duckdb
        raise RuntimeError(
            f"The kitelake package could not be loaded ({exc}). Install its dependencies:\n"
            f"    {_REPO_ROOT}/.venv-kitelake/bin/pip install -r {_REPO_ROOT}/kitelake/requirements.txt"
        ) from exc


def _unavailable(reason: str, guidance: list[str] | None = None) -> dict[str, Any]:
    return {
        "available": False,
        "root": "",
        "label": "",
        "reason": reason,
        "guidance": guidance or [],
        "candidates": [],
        "known": [],
        "free_gib": 0.0,
        "total_gib": 0.0,
    }


# ─── models ──────────────────────────────────────────────────────────────────
class AdoptRootRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Absolute folder path to store data in")
    label: str = Field("", max_length=80, description="Friendly name shown in the UI")
    create: bool = Field(True, description="Create the folder if it does not exist")


class ActivateRootRequest(BaseModel):
    lake_id: str = Field(..., min_length=4)


class PlanRequest(BaseModel):
    universe: str = Field("nse-all", min_length=1)
    interval: str = Field("minute")
    frm: str = Field(..., description="YYYY-MM-DD")
    to: str = Field(..., description="YYYY-MM-DD")
    rate: float = Field(2.5, gt=0, le=3.0)


# ─── status / volumes / browse ───────────────────────────────────────────────
@router.get("/status")
def get_status(_user: UserContext = Depends(get_current_user)) -> dict[str, Any]:
    """Where the data lives and whether it is reachable. Never fails."""
    try:
        kl = _kitelake()
    except RuntimeError as exc:
        return _unavailable(str(exc).splitlines()[0], [str(exc)])
    try:
        status = kl.lake_status().to_dict()
    except Exception as exc:  # defensive: status must always answer
        logger.warning("datalake status failed: %s", exc)
        return _unavailable(f"Could not inspect the data folder: {exc}")

    # Add a credential hint so the UI can show the whole readiness picture at once.
    try:
        from kitelake.config import have_credentials  # noqa: PLC0415

        status["has_credentials"] = have_credentials()
    except Exception:
        status["has_credentials"] = False
    try:
        from kitelake.instruments import master_age  # noqa: PLC0415

        status["instrument_master_age_hours"] = master_age() if status.get("available") else None
    except Exception:
        status["instrument_master_age_hours"] = None
    return status


@router.get("/volumes")
def list_volumes(_user: UserContext = Depends(get_current_user)) -> dict[str, Any]:
    """Mounted volumes the data could live on, with free space and lake detection."""
    try:
        kl = _kitelake()
    except RuntimeError as exc:
        return {"volumes": [], "error": str(exc)}
    try:
        return {"volumes": [v.to_dict() for v in kl.list_volumes()], "error": ""}
    except Exception as exc:
        logger.warning("datalake volumes failed: %s", exc)
        return {"volumes": [], "error": f"Could not enumerate volumes: {exc}"}


@router.get("/browse")
def browse(
    path: Optional[str] = Query(None, description="Folder to list; defaults to home"),
    show_hidden: bool = Query(False),
    _user: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    """List sub-folders for the folder picker.

    Only directory *names* are returned — never file contents — because the caller is
    choosing a location, not reading data.
    """
    try:
        kl = _kitelake()
    except RuntimeError as exc:
        return {"path": "", "parent": "", "entries": [], "error": str(exc), "writable": False}
    try:
        return kl.browse(path, show_hidden=show_hidden)
    except Exception as exc:
        logger.warning("datalake browse failed: %s", exc)
        return {
            "path": path or "", "parent": "", "entries": [], "writable": False,
            "error": f"Could not list that folder: {exc}",
        }


# ─── mutate the root ─────────────────────────────────────────────────────────
@router.post("/root")
def adopt_root(
    payload: AdoptRootRequest, _user: UserContext = Depends(get_current_user)
) -> dict[str, Any]:
    """Point the lake at a folder, stamping and registering it."""
    kl = _import_or_400()
    from kitelake.volume import LakeUnavailable  # noqa: PLC0415

    try:
        status = kl.adopt_root(payload.path, label=payload.label, create=payload.create)
    except LakeUnavailable as exc:
        # The user picked somewhere unusable (e.g. a root-owned mount point). This IS a
        # client error — they must choose differently or fix permissions — so 400 with
        # the full remediation text, which includes the exact chown command.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("datalake adopt_root failed")
        raise HTTPException(status_code=500, detail=f"Could not use that folder: {exc}") from exc
    return status.to_dict()


@router.post("/root/activate")
def activate_root(
    payload: ActivateRootRequest, _user: UserContext = Depends(get_current_user)
) -> dict[str, Any]:
    """Switch to a previously-registered folder."""
    kl = _import_or_400()
    from kitelake.volume import LakeUnavailable, set_active  # noqa: PLC0415

    try:
        return set_active(payload.lake_id).to_dict()
    except LakeUnavailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/root/{lake_id}")
def forget_root(
    lake_id: str, _user: UserContext = Depends(get_current_user)
) -> dict[str, Any]:
    """Unregister a folder. The stored data is never touched."""
    _import_or_400()
    from kitelake.volume import forget_root as _forget  # noqa: PLC0415

    return _forget(lake_id).to_dict()


# ─── lake contents ───────────────────────────────────────────────────────────
@router.get("/summary")
def summary(
    interval: str = Query("minute"), _user: UserContext = Depends(get_current_user)
) -> dict[str, Any]:
    """Ledger progress plus what is stored. Degrades to ``available: false``."""
    try:
        kl = _kitelake()
    except RuntimeError as exc:
        return {**_unavailable(str(exc).splitlines()[0]), "stats": {}, "runs": []}
    from kitelake.volume import LakeUnavailable  # noqa: PLC0415

    try:
        status = kl.lake_status()
        if not status.available:
            return {**status.to_dict(), "stats": {}, "runs": []}
        from kitelake.manifest import Manifest  # noqa: PLC0415

        with Manifest() as man:
            return {
                **status.to_dict(),
                "stats": man.stats(interval),
                "runs": man.runs(8),
            }
    except LakeUnavailable as exc:
        return {**_unavailable(str(exc).splitlines()[0]), "stats": {}, "runs": []}
    except Exception as exc:
        logger.warning("datalake summary failed: %s", exc)
        return {**_unavailable(f"Could not read the ledger: {exc}"), "stats": {}, "runs": []}


@router.get("/presets")
def presets(_user: UserContext = Depends(get_current_user)) -> dict[str, Any]:
    """Universe presets with live instrument counts where the master is available."""
    try:
        _kitelake()
        from kitelake.universe import OUT_OF_SCOPE, PRESETS, TIERS, preset_counts  # noqa: PLC0415
    except Exception as exc:
        return {"presets": [], "tiers": [], "out_of_scope": {}, "error": str(exc)}
    counts: dict[str, int] = {}
    note = ""
    try:
        counts = preset_counts()
    except Exception as exc:
        note = f"counts unavailable ({exc}); sync the instrument master first"
    return {
        "presets": [
            {
                "name": name,
                "description": desc,
                "count": counts.get(name),
                "tier": TIERS.index(name) + 1 if name in TIERS else None,
            }
            for name, desc in PRESETS.items()
        ],
        "tiers": list(TIERS),
        "out_of_scope": OUT_OF_SCOPE,
        "note": note,
        "error": "",
    }


@router.get("/tiers")
def tiers(
    interval: str = Query("minute"),
    frm: str = Query(..., description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    rate: float = Query(2.5, gt=0, le=3.0),
    _user: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Cost the three supported universes as nested tiers.

    The tiers overlap, so the useful numbers are the incremental ones: summing per-tier
    costs double-counts ~41,000 requests that the ledger skips automatically.
    """
    _import_or_400()
    from datetime import date  # noqa: PLC0415

    from kitelake.universe import tier_plan  # noqa: PLC0415
    from kitelake.volume import LakeUnavailable  # noqa: PLC0415

    try:
        start, end = date.fromisoformat(frm), date.fromisoformat(to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"bad date: {exc}") from exc
    try:
        return tier_plan(interval, start, end, rate=rate)
    except (LakeUnavailable, FileNotFoundError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/plan")
def plan(
    payload: PlanRequest, _user: UserContext = Depends(get_current_user)
) -> dict[str, Any]:
    """Estimate requests, wall-clock and disk for a download. Makes no network calls."""
    _import_or_400()
    from datetime import date  # noqa: PLC0415

    from kitelake.universe import estimate_cost, resolve_universe  # noqa: PLC0415
    from kitelake.volume import LakeUnavailable  # noqa: PLC0415

    try:
        frm = date.fromisoformat(payload.frm)
        to = date.fromisoformat(payload.to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"bad date: {exc}") from exc
    try:
        instruments = resolve_universe(payload.universe)
        return estimate_cost(instruments, payload.interval, frm, to, rate=payload.rate)
    except LakeUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/symbols")
def symbols(
    interval: str = Query("minute"),
    search: str = Query("", max_length=64),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    sort: str = Query("rows", pattern="^(rows|tradingsymbol|first_ts|last_ts|bytes)$"),
    _user: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Instruments actually stored in the lake, for the data browser.

    Pagination, search and sort all happen in SQL. Loading every stored row and slicing in
    Python made this endpoint slow enough — reading 7,400+ rows off the removable drive per
    call — to noticeably degrade the API when the UI polled it.
    """
    try:
        kl = _kitelake()
    except RuntimeError as exc:
        return {**_unavailable(str(exc).splitlines()[0]), "symbols": [], "total": 0}
    from kitelake.volume import LakeUnavailable  # noqa: PLC0415

    try:
        status = kl.lake_status()
        if not status.available:
            return {**status.to_dict(), "symbols": [], "total": 0}
        from kitelake.manifest import Manifest  # noqa: PLC0415

        with Manifest() as man:
            page, total = man.symbols_page(
                interval, search=search.strip(), sort=sort, limit=limit, offset=offset
            )
    except LakeUnavailable as exc:
        return {**_unavailable(str(exc).splitlines()[0]), "symbols": [], "total": 0}
    except Exception as exc:
        logger.warning("datalake symbols failed: %s", exc)
        return {
            **_unavailable(f"Could not list stored instruments: {exc}"),
            "symbols": [], "total": 0,
        }

    return {"available": True, "interval": interval, "total": total, "symbols": page}


@router.get("/bars")
def bars(
    symbol: str = Query(..., min_length=1, max_length=64),
    interval: str = Query("minute"),
    frm: Optional[str] = Query(None),
    to: Optional[str] = Query(None),
    limit: int = Query(1500, ge=10, le=20000),
    _user: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    """OHLCV for one instrument, for charting.

    Reads the parquet with **pyarrow only** — deliberately not via ``kitelake.reader``,
    which needs polars. The Sterling backend interpreter has pyarrow but not polars, and
    keeping this endpoint dependency-light is what lets the UI work without changing the
    backend's environment.

    When the range holds more bars than ``limit``, it downsamples by striding rather than
    truncating, so a chart still shows the whole period instead of just its first slice.
    """
    _import_or_400()
    from datetime import datetime, timezone  # noqa: PLC0415

    import pyarrow.compute as pc  # noqa: PLC0415
    import pyarrow.parquet as pq  # noqa: PLC0415

    from kitelake.config import IST, PRICE_SCALE  # noqa: PLC0415
    from kitelake.manifest import Manifest  # noqa: PLC0415
    from kitelake.schema import sanitize_symbol  # noqa: PLC0415
    from kitelake.volume import LakeUnavailable, bars_dir  # noqa: PLC0415

    try:
        base = bars_dir(create=False)
    except LakeUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc).splitlines()[0]) from exc

    # Resolve the symbol (or token) to its single parquet file.
    token: int | None = None
    row: dict[str, Any] | None = None
    with Manifest() as man:
        if symbol.isdigit():
            token = int(symbol)
            row = man.instrument(token)
        else:
            matches = man.find_instruments(symbol)
            if matches:
                row = matches[0]
                token = int(row["instrument_token"])
    if token is None:
        raise HTTPException(status_code=404, detail=f"Unknown instrument {symbol!r}.")

    matches = sorted(base.glob(f"interval={interval}/**/{token}__*.parquet"))
    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"No {interval} bars stored for {symbol!r} yet — it may not have been "
                   "downloaded, or Kite returned no trades for it.",
        )

    try:
        table = pq.ParquetFile(matches[0]).read()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read the bar file: {exc}") from exc

    def _bound(text: str | None, end: bool) -> int | None:
        if not text:
            return None
        try:
            day = datetime.fromisoformat(text)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"bad date {text!r}") from None
        if day.tzinfo is None:
            day = day.replace(tzinfo=IST)
        if end and day.hour == 0 and day.minute == 0:
            day = day.replace(hour=23, minute=59, second=59)
        return int(day.astimezone(timezone.utc).timestamp() * 1_000_000)

    lo, hi = _bound(frm, False), _bound(to, True)
    if lo is not None or hi is not None:
        ts_us = pc.cast(table.column("ts"), "int64")
        mask = None
        if lo is not None:
            mask = pc.greater_equal(ts_us, lo)
        if hi is not None:
            upper = pc.less_equal(ts_us, hi)
            mask = upper if mask is None else pc.and_(mask, upper)
        table = table.filter(mask)

    total = table.num_rows
    stride = max(1, -(-total // limit))  # ceil division: keep the full span, thin it out
    if stride > 1:
        table = table.take(list(range(0, total, stride)))

    ts = table.column("ts").to_pylist()
    o, h, l, c, v = (table.column(k).to_pylist() for k in ("open", "high", "low", "close", "volume"))
    scale = float(PRICE_SCALE)
    return {
        "symbol": (row or {}).get("tradingsymbol") or symbol,
        "instrument_token": token,
        "exchange": (row or {}).get("exchange") or "",
        "interval": interval,
        "rows_total": total,
        "rows_returned": table.num_rows,
        "downsampled_every": stride,
        "bars": [
            {
                "t": ts[i].astimezone(IST).isoformat(),
                "o": o[i] / scale, "h": h[i] / scale, "l": l[i] / scale, "c": c[i] / scale,
                "v": v[i],
            }
            for i in range(table.num_rows)
        ],
    }


@router.get("/hot")
def hot(
    limit: int = Query(60, ge=1, le=2000),
    greeks_only: bool = Query(False),
    _user: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Live enriched quotes from a tick pipeline running *in this process*.

    The hot store is in-process memory, so this only returns data when the pipeline was
    started inside the backend. A pipeline run from the CLI has its own store that this
    process cannot see — that is a real limitation of choosing memory over Redis, and
    ``running: false`` says so plainly rather than looking like an empty market.
    """
    try:
        _kitelake()
        from kitelake.pipeline import get_pipeline  # noqa: PLC0415
    except Exception as exc:
        return {"running": False, "reason": str(exc).splitlines()[0], "quotes": []}

    pipe = get_pipeline()
    if pipe is None:
        return {
            "running": False,
            "reason": "No tick pipeline is running in the backend process.",
            "hint": "Ticks are only hot for the process that ingests them. Start one in-process, "
                    "or run `kitelake pipe` and read it there with `kitelake hot`.",
            "quotes": [],
        }
    try:
        return {
            "running": True,
            "status": pipe.status(),
            "quotes": pipe.snapshot(limit=limit, with_greeks_only=greeks_only),
        }
    except Exception as exc:
        logger.warning("datalake hot failed: %s", exc)
        return {"running": False, "reason": f"Could not read the hot store: {exc}", "quotes": []}


def _import_or_400() -> Any:
    """Like :func:`_kitelake` but for mutating endpoints, where a 500/400 is appropriate."""
    try:
        return _kitelake()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
