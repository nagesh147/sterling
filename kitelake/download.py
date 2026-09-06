"""The download orchestrator: resumable, interruptible, and honest about failure.

Shape of the thing: the work list is *chunks*, not instruments. Every chunk is planned
into the SQLite ledger up front, then a bounded pool of workers drains whatever is still
pending. That is what makes resume real — kill the process at any point, restart, and only
the unfinished chunks are fetched. It also makes the progress percentage meaningful.

Three failure behaviours that took deliberate design:

**A dead token aborts the whole run, immediately.** Kite returns HTTP 400 for an invalid
api_key (verified against the live API), so the naive classification would mark each chunk
``failed`` and move on. Forty thousand chunks later you would have an empty lake, a ledger
full of ``failed``, and a resume that skips them all. Instead the first
:class:`~kitelake.fetcher.KitelakeFatal` cancels every worker and leaves those chunks
``pending``, so resuming after ``kitelake auth`` just works.

**Empty is not failed.** An illiquid instrument, or a window before the contract listed,
returns zero candles. That is recorded as ``empty`` and never retried.

**Ctrl-C finishes what it started.** SIGINT stops scheduling new chunks but lets in-flight
writes complete, so the parquet on disk is always valid and the ledger always agrees with
it. Then it prints the exact command to resume.

Writes go through ``asyncio.to_thread`` because parquet encoding is CPU-bound; doing it on
the event loop would stall the fetch pipeline and waste the rate-limit budget.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import signal
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from .config import DEFAULT_RATE, VALID_INTERVALS, Credentials, load_credentials
from .fetcher import (
    KiteHistoricalFetcher,
    KitelakeFatal,
    KitelakeInputError,
    KitelakeInstrumentRejected,
    chunk_range,
)
from .ratelimit import AdaptiveLimiter
from .runlock import DownloadInProgress, download_lock

__all__ = [
    "run_download", "download", "run_tiered_download", "download_tiers",
    "DownloadInProgress",
]

ProgressFn = Callable[[dict[str, Any]], None]


class _EventLog:
    """Append-only JSONL run log. Credentials never enter this file."""

    _FORBIDDEN = ("api_key", "access_token", "api_secret", "authorization")

    def __init__(self, path: Path | None) -> None:
        self._handle = None
        if path is not None:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._handle = open(path, "a", encoding="utf-8")
            except OSError:
                self._handle = None

    def write(self, **payload: Any) -> None:
        if self._handle is None:
            return
        clean = {k: v for k, v in payload.items() if k.lower() not in self._FORBIDDEN}
        clean.setdefault("t", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        try:
            self._handle.write(json.dumps(clean, default=str) + "\n")
            self._handle.flush()
        except (OSError, TypeError):
            pass

    def close(self) -> None:
        if self._handle is not None:
            with contextlib.suppress(OSError):
                self._handle.close()
            self._handle = None


def _wants_oi(instrument: Any, mode: str) -> bool:
    if mode == "on":
        return True
    if mode == "off":
        return False
    # 'auto': open interest exists only for derivatives, and asking for it costs nothing.
    return bool(getattr(instrument, "is_derivative", False))


async def run_download(
    universe: str,
    interval: str = "minute",
    frm: date | None = None,
    to: date | None = None,
    *,
    oi: str = "auto",
    continuous: bool = False,
    concurrency: int = 6,
    rate: float = DEFAULT_RATE,
    resume: bool = True,
    retry_failed: bool = False,
    dry_run: bool = False,
    creds: Credentials | None = None,
    transport: Any = None,
    progress: ProgressFn | None = None,
    root: Any = None,
) -> dict[str, Any]:
    """Download ``universe`` for ``interval`` over ``[frm, to]``. Returns a run summary."""
    from .config import CONTINUOUS_INTERVALS

    if continuous and interval not in CONTINUOUS_INTERVALS:
        # Every request in the run would 400. Refusing here costs one line; finding
        # out from the API costs a full pass that marks every chunk failed, and a
        # ledger of failures a later --resume has to be told to ignore.
        raise ValueError(
            f"--continuous is not available for interval {interval!r}: Kite serves "
            f"continuous data only for {', '.join(sorted(CONTINUOUS_INTERVALS))}. "
            f"Intraday futures history is limited to the current contract's own life "
            f"(about three months); expired contracts are not served at all.")
    from .manifest import Manifest
    from .universe import estimate_cost, resolve_universe
    from .volume import logs_dir
    from .writer import append_candles

    if interval not in VALID_INTERVALS:
        raise ValueError(f"invalid interval {interval!r}; expected one of {', '.join(VALID_INTERVALS)}")
    if frm is None or to is None:
        raise ValueError("both 'frm' and 'to' are required")
    if to < frm:
        raise ValueError(f"'to' ({to}) is before 'from' ({frm})")
    if oi not in {"auto", "on", "off"}:
        raise ValueError("oi must be 'auto', 'on' or 'off'")

    instruments = resolve_universe(universe, root=root)
    by_token = {i.token: i for i in instruments}
    plan = estimate_cost(instruments, interval, frm, to, rate=rate)

    def emit(**payload: Any) -> None:
        if progress:
            progress(payload)

    if dry_run:
        emit(event="dry_run", **plan)
        return {
            "dry_run": True, "universe": universe, **plan,
            "note": "No requests made. Drop --dry-run to start.",
        }

    if creds is None and transport is None:
        creds = load_credentials()  # raises CredentialsMissing with remediation text
    creds = creds or Credentials("test", "test")

    # One writer per lake, enforced by the OS. BarWriter's per-file lock only covers this
    # process's threads; a second download process shares nothing with it and would clobber
    # the same parquet files. See kitelake.runlock.
    with download_lock(root, note=f"{universe} {interval} {frm}..{to}"):
        return await _run_download_locked(
            universe, interval, frm, to, oi=oi, continuous=continuous,
            concurrency=concurrency, rate=rate, resume=resume,
            retry_failed=retry_failed, creds=creds, transport=transport,
            progress=progress, root=root, plan=plan,
            instruments=instruments, by_token=by_token,
        )


async def _run_download_locked(
    universe: str,
    interval: str,
    frm: date,
    to: date,
    *,
    oi: str,
    continuous: bool,
    concurrency: int,
    rate: float,
    resume: bool,
    retry_failed: bool,
    creds: Credentials,
    transport: Any,
    progress: ProgressFn | None,
    root: Any,
    plan: dict[str, Any],
    instruments: list[Any],
    by_token: dict[int, Any],
) -> dict[str, Any]:
    """The body of :func:`run_download`, executed while holding the single-writer lock."""
    from .manifest import Manifest
    from .volume import logs_dir
    from .writer import append_candles

    def emit(**payload: Any) -> None:
        if progress:
            progress(payload)

    man = Manifest(root=root)
    log: _EventLog | None = None
    try:
        # ── plan every chunk into the ledger ────────────────────────────────
        man.upsert_instruments(
            [
                {
                    "instrument_token": i.token, "tradingsymbol": i.tradingsymbol,
                    "name": i.name, "exchange": i.exchange, "segment": i.segment,
                    "instrument_type": i.instrument_type, "expiry": i.expiry or "",
                    "strike": i.strike, "tick_size": i.tick_size, "lot_size": i.lot_size,
                }
                for i in instruments
            ]
        )
        chunks = chunk_range(frm, to, interval)
        for inst in instruments:
            man.plan_chunks(inst.token, interval, chunks)

        if not resume:
            man.reset_chunks(interval, [i.token for i in instruments])
        pending = man.pending_chunks(
            interval, [i.token for i in instruments], retry_failed=retry_failed
        )

        run_id = man.start_run(
            universe=universe, interval=interval, frm=frm, to=to, requested=len(pending)
        )
        try:
            log = _EventLog(logs_dir(root) / f"download-{run_id}.jsonl")
        except Exception:
            log = _EventLog(None)

        stats = {
            "done": 0, "empty": 0, "failed": 0, "skipped": 0, "rows": 0, "bytes": 0,
            "requests": 0, "skipped_existing": len(instruments) * len(chunks) - len(pending),
        }
        started = time.perf_counter()
        limiter = AdaptiveLimiter(rate)
        fatal: BaseException | None = None
        stopping = asyncio.Event()

        log.write(
            event="run_start", run_id=run_id, universe=universe, interval=interval,
            frm=str(frm), to=str(to), instruments=len(instruments),
            chunks_pending=len(pending), chunks_total=len(instruments) * len(chunks),
            rate=rate, concurrency=concurrency,
        )
        emit(
            event="start", run_id=run_id, instruments=len(instruments),
            chunks=len(pending), already_done=stats["skipped_existing"], eta=plan["eta_human"],
        )

        # ── graceful SIGINT: stop scheduling, let in-flight work land ────────
        loop = asyncio.get_running_loop()
        previous: dict[int, Any] = {}

        def _on_signal() -> None:
            if not stopping.is_set():
                stopping.set()
                emit(event="interrupt", message="finishing in-flight chunks, then stopping")

        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError, ValueError):
                previous[sig] = signal.getsignal(sig)
                loop.add_signal_handler(sig, _on_signal)

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        for item in pending:
            queue.put_nowait(item)

        # Every worker's fetcher registers here so the summary can report the true HTTP
        # request count (which includes retries), not just the chunk count.
        fetchers_seen: list[KiteHistoricalFetcher] = []

        def sum_requests() -> int:
            return sum(f.requests_made for f in fetchers_seen)

        async def worker(_n: int) -> None:
            nonlocal fatal
            async with KiteHistoricalFetcher(
                creds, limiter=limiter, transport=transport,
                on_event=lambda p: log.write(**p) if log else None,
            ) as fetcher:
                fetchers_seen.append(fetcher)
                while not stopping.is_set():
                    try:
                        item = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    token = int(item["instrument_token"])
                    inst = by_token.get(token)
                    if inst is None:
                        man.mark_chunk(token, interval, item["chunk_from"], "skipped")
                        continue
                    c_from = date.fromisoformat(item["chunk_from"])
                    c_to = date.fromisoformat(item["chunk_to"])
                    try:
                        candles = await fetcher.fetch_chunk(
                            token, interval, c_from, c_to,
                            continuous=continuous and inst.instrument_type == "FUT",
                            oi=_wants_oi(inst, oi),
                            exchange=inst.exchange or "NSE",
                        )
                    except KitelakeFatal as exc:
                        # Leave this chunk pending: it was never actually attempted in a
                        # way that tells us anything about the data.
                        fatal = exc
                        stopping.set()
                        log.write(event="fatal", token=token, error=str(exc)[:400])
                        return
                    except KitelakeInstrumentRejected as exc:
                        # Kite will never serve this instrument. Recording it 'skipped'
                        # rather than 'failed' keeps --retry-failed from spending a
                        # request on it on every future run.
                        man.mark_chunk(token, interval, item["chunk_from"], "skipped", error=str(exc))
                        stats["skipped"] += 1
                        log.write(event="chunk_skipped", token=token,
                                  chunk_from=item["chunk_from"], error=str(exc)[:300])
                        continue
                    except KitelakeInputError as exc:
                        man.mark_chunk(token, interval, item["chunk_from"], "failed", error=str(exc))
                        stats["failed"] += 1
                        log.write(event="chunk_failed", token=token,
                                  chunk_from=item["chunk_from"], error=str(exc)[:300])
                        continue
                    except Exception as exc:  # transport exhausted its retries
                        man.mark_chunk(token, interval, item["chunk_from"], "failed", error=str(exc))
                        stats["failed"] += 1
                        log.write(event="chunk_failed", token=token,
                                  chunk_from=item["chunk_from"], error=str(exc)[:300])
                        continue

                    stats["requests"] = sum_requests()
                    if not candles:
                        man.mark_chunk(token, interval, item["chunk_from"], "empty")
                        stats["empty"] += 1
                        log.write(event="chunk_empty", token=token, chunk_from=item["chunk_from"])
                        continue

                    # Parquet encoding is CPU-bound: keep it off the event loop so the
                    # fetch pipeline never idles against the rate limit.
                    try:
                        written = await asyncio.to_thread(
                            append_candles, inst, interval, candles,
                            with_oi=_wants_oi(inst, oi), root=root,
                        )
                    except Exception as exc:
                        man.mark_chunk(token, interval, item["chunk_from"], "failed", error=f"write: {exc}")
                        stats["failed"] += 1
                        log.write(event="write_failed", token=token, error=str(exc)[:300])
                        continue

                    man.mark_chunk(token, interval, item["chunk_from"], "done", rows=len(candles))
                    man.upsert_symbol(
                        token, interval,
                        tradingsymbol=inst.tradingsymbol, exchange=inst.exchange,
                        segment=inst.segment, path=written["path"], rows=written["rows"],
                        bytes=written["bytes"], first_ts=written["first_ts"],
                        last_ts=written["last_ts"], sha256=written["sha256"], status="ok",
                    )
                    stats["done"] += 1
                    stats["rows"] += len(candles)
                    stats["bytes"] = max(stats["bytes"], 0) + written["bytes"]
                    if stats["done"] % 25 == 0 or stats["done"] == 1:
                        done = stats["done"] + stats["empty"] + stats["failed"]
                        elapsed = max(time.perf_counter() - started, 0.001)
                        remaining = max(len(pending) - done, 0)
                        emit(
                            event="progress", done=done, total=len(pending),
                            pct=round(100.0 * done / len(pending), 1) if pending else 100.0,
                            rows=stats["rows"], rate=round(limiter.current_rate, 2),
                            rq_s=round(done / elapsed, 2),
                            eta_s=int(remaining / max(done / elapsed, 0.01)),
                            symbol=inst.tradingsymbol,
                        )

        workers = [asyncio.create_task(worker(i)) for i in range(max(1, concurrency))]
        await asyncio.gather(*workers, return_exceptions=True)

        for sig, handler in previous.items():
            with contextlib.suppress(NotImplementedError, ValueError):
                loop.remove_signal_handler(sig)

        elapsed = time.perf_counter() - started
        man.finish_run(
            run_id, completed=stats["done"], failed=stats["failed"], empty=stats["empty"],
            rows=stats["rows"], bytes=stats["bytes"],
            notes="interrupted" if stopping.is_set() and not fatal else ("fatal" if fatal else "ok"),
        )
        ledger = man.stats(interval)
        log.write(event="run_end", run_id=run_id, elapsed_s=round(elapsed, 1), **stats)

        summary: dict[str, Any] = {
            "run_id": run_id,
            "universe": universe,
            "interval": interval,
            "frm": str(frm),
            "to": str(to),
            "instruments": len(instruments),
            "chunks_attempted": len(pending),
            "chunks_already_done": stats["skipped_existing"],
            **{k: v for k, v in stats.items() if k != "skipped_existing"},
            "elapsed_s": round(elapsed, 1),
            "elapsed_human": f"{elapsed/60:.1f}m" if elapsed > 90 else f"{elapsed:.1f}s",
            "gib": round(stats["bytes"] / 2**30, 4),
            "ledger": ledger,
            "interrupted": stopping.is_set() and fatal is None,
            "fatal": None,
            "resume_command": (
                f"kitelake download {universe} --interval {interval} "
                f"--from {frm} --to {to} --resume"
            ),
        }
        if fatal is not None:
            summary["fatal"] = str(fatal)
            summary["note"] = (
                "Run aborted on a fatal credential/entitlement error. The unfinished "
                "chunks are still marked pending, so nothing was lost — fix the cause and "
                "re-run the resume command."
            )
        elif summary["interrupted"]:
            summary["note"] = "Interrupted. Re-run the resume command to continue."
        return summary
    finally:
        if log is not None:
            log.close()
        man.close()


async def run_tiered_download(
    interval: str = "minute",
    frm: date | None = None,
    to: date | None = None,
    *,
    tiers: Sequence[str] | None = None,
    stop_after: str | None = None,
    progress: ProgressFn | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Download the supported universes in tier order, widening as it goes.

    The three tiers are nested (their union is exactly ``equity-all``), so this is not
    three jobs — it is one job with useful checkpoints. Tier 1 finishes in minutes and is
    immediately queryable; each later tier only fetches instruments no earlier tier
    covered, because the ledger settles work per chunk. Running all three costs the same
    as going straight to the widest tier.

    A fatal error (dead token, missing entitlement) stops the whole sequence rather than
    marching through the remaining tiers to fail identically.
    """
    from .universe import TIERS, tier_plan

    order = list(tiers) if tiers else list(TIERS)
    if stop_after:
        if stop_after not in order:
            raise ValueError(f"stop_after must be one of {', '.join(order)}")
        order = order[: order.index(stop_after) + 1]

    if kwargs.get("dry_run"):
        # Delegate to tier_plan rather than summing per-tier estimates: a standalone
        # estimate per tier double-counts the nested overlap and would advertise ~132,000
        # requests for a job that really issues ~91,000.
        plan = tier_plan(
            interval, frm, to,
            rate=kwargs.get("rate", DEFAULT_RATE),
            master=None,
            root=kwargs.get("root"),
        )
        plan["tiers"] = [t for t in plan["tiers"] if t["universe"] in order]
        if plan["tiers"]:
            last = plan["tiers"][-1]
            plan["total_requests"] = last["cumulative_requests"]
            plan["total_gib"] = last["cumulative_gib"]
            plan["total_eta"] = last["cumulative_eta"]
            plan["total_instruments"] = sum(t["new_instruments"] for t in plan["tiers"])
        plan["dry_run"] = True
        plan["tiers_requested"] = len(order)
        plan["note"] = "No requests made. Drop --dry-run to start."
        return plan

    results: list[dict[str, Any]] = []
    started = time.perf_counter()

    def emit(**payload: Any) -> None:
        if progress:
            progress(payload)

    for position, universe in enumerate(order, start=1):
        emit(event="tier_start", tier=position, of=len(order), universe=universe)
        summary = await run_download(
            universe, interval, frm, to, progress=progress, **kwargs
        )
        summary["tier"] = position
        results.append(summary)
        emit(
            event="tier_end", tier=position, universe=universe,
            done=summary.get("done", 0), rows=summary.get("rows", 0),
            already_done=summary.get("chunks_already_done", 0),
        )
        if summary.get("fatal"):
            emit(event="tier_abort", tier=position, universe=universe, error=summary["fatal"])
            break
        if summary.get("interrupted"):
            emit(event="tier_interrupted", tier=position, universe=universe)
            break

    elapsed = time.perf_counter() - started
    completed = [r for r in results if not r.get("fatal") and not r.get("interrupted")]
    return {
        "tiers": results,
        "tiers_completed": len(completed),
        "tiers_requested": len(order),
        "rows": sum(r.get("rows", 0) for r in results),
        "chunks_done": sum(r.get("done", 0) for r in results),
        "chunks_empty": sum(r.get("empty", 0) for r in results),
        "chunks_failed": sum(r.get("failed", 0) for r in results),
        "requests": sum(r.get("requests", 0) for r in results),
        "elapsed_s": round(elapsed, 1),
        "elapsed_human": f"{elapsed / 3600:.1f}h" if elapsed > 5400 else f"{elapsed / 60:.1f}m",
        "fatal": next((r["fatal"] for r in results if r.get("fatal")), None),
        "interrupted": any(r.get("interrupted") for r in results),
        "resume_command": (
            f"kitelake download --tiers --interval {interval} --from {frm} --to {to}"
        ),
    }


def download(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Blocking wrapper around :func:`run_download`."""
    return asyncio.run(run_download(*args, **kwargs))


def download_tiers(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Blocking wrapper around :func:`run_tiered_download`."""
    return asyncio.run(run_tiered_download(*args, **kwargs))
