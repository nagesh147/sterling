"""``kitelake`` command line. Every command must fail *informatively*, never with a traceback.

Two rules shape this file:

1. **Sub-module imports happen inside the command functions.** ``--help`` must work with a
   broken lake, a missing optional dependency, or no credentials.
2. **A missing data volume is a message, not a crash.** Commands that need the lake catch
   :class:`~kitelake.volume.LakeUnavailable` and print its guidance plus how to fix it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from typing import Any, Sequence

__all__ = ["main", "build_parser"]

_OK = 0
_ERR = 1


# ─── output helpers ──────────────────────────────────────────────────────────
def _die(message: str, *, hint: str = "") -> int:
    print(f"error: {message}", file=sys.stderr)
    if hint:
        print(f"\n{hint}", file=sys.stderr)
    return _ERR


def _table(rows: Sequence[Sequence[Any]], headers: Sequence[str]) -> str:
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    out = [line, "  ".join("-" * w for w in widths)]
    for row in rows:
        out.append("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))
    return "\n".join(out)


def _parse_date(text: str | None, *, default_days_ago: int | None = None) -> date | None:
    if text:
        try:
            return date.fromisoformat(text)
        except ValueError as exc:
            raise SystemExit(f"error: bad date {text!r} — use YYYY-MM-DD") from exc
    if default_days_ago is not None:
        return date.today() - timedelta(days=default_days_ago)
    return None


def _show_unavailable(status: Any) -> int:
    """Render a LakeStatus / LakeUnavailable guidance block."""
    print("The market-data folder is not available right now.\n")
    reason = getattr(status, "reason", "") or ""
    if reason:
        print(f"  {reason}\n")
    for line in getattr(status, "guidance", []) or []:
        print(f"  - {line}")
    print("\nSet it up with:")
    print("    kitelake root --pick            # graphical folder chooser")
    print("    kitelake root --set /path/to/folder")
    return _ERR


def _guarded(fn, *args: Any, **kwargs: Any) -> int:
    """Run a command, converting expected failures into readable messages."""
    from .config import CredentialsMissing
    from .download import DownloadInProgress
    from .volume import LakeUnavailable, lake_status

    try:
        return fn(*args, **kwargs)
    except DownloadInProgress as exc:
        # Refusing a second writer is correct behaviour, not a crash — print the guidance.
        print(str(exc), file=sys.stderr)
        return _ERR
    except LakeUnavailable:
        return _show_unavailable(lake_status())
    except CredentialsMissing as exc:
        return _die("no Kite credentials", hint=str(exc))
    except FileNotFoundError as exc:
        return _die(str(exc))
    except (ValueError, LookupError) as exc:
        return _die(str(exc))
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


# ─── commands ────────────────────────────────────────────────────────────────
def cmd_root(args: argparse.Namespace) -> int:
    from .volume import (
        adopt_root, forget_root, lake_status, list_volumes, pick_directory_gui, set_active,
    )
    from .config import DEFAULT_LAKE_DIRNAME

    if args.list:
        status = lake_status()
        print(f"active: {status.root or '(none)'}"
              + (f"  [{status.label}]" if status.label else ""))
        print(f"available: {status.available}\n")
        rows = [
            [
                "*" if k.get("lake_id") == status.lake_id else " ",
                (k.get("label") or "")[:28],
                k.get("last_path") or "",
                (k.get("lake_id") or "")[:8],
            ]
            for k in status.known
        ]
        if rows:
            print("known data folders:")
            print(_table(rows, ["", "label", "path", "id"]))
        else:
            print("no data folders registered yet")
        print("\nmounted volumes:")
        vrows = [
            [
                v.path, v.fstype, f"{v.free_gib:g}", f"{v.total_gib:g}",
                "yes" if v.writable else "no", "yes" if v.removable else "no",
                v.lake_label or ("lake" if v.lake_at else ""),
            ]
            for v in list_volumes()
        ]
        print(_table(vrows, ["mount", "fs", "free GiB", "total", "writable", "removable", "lake"]))
        return _OK

    if args.forget:
        status = forget_root(args.forget)
        print(f"forgot {args.forget} (data left untouched); active is now {status.root or '(none)'}")
        return _OK

    if args.use:
        status = set_active(args.use)
        print(f"active data folder: {status.root}")
        return _OK

    target = args.set
    if args.pick:
        volumes = [v for v in list_volumes() if v.writable and v.free_bytes > 2**30]
        initial = volumes[0].path if volumes else None
        chosen = pick_directory_gui(initial)
        if not chosen:
            print("cancelled — no folder chosen")
            return _OK
        target = chosen
        # If they picked a bare volume root, put the lake in a named subfolder rather
        # than scattering bars/ and manifest/ across the whole drive.
        from pathlib import Path as _P

        picked = _P(target)
        from .volume import LakeStamp

        if LakeStamp.read(picked) is None and any(
            str(picked) == v.path for v in list_volumes()
        ):
            target = str(picked / DEFAULT_LAKE_DIRNAME)
            print(f"using {target} (a subfolder, so the drive root stays tidy)")

    if not target:
        status = lake_status()
        if status.available:
            print(f"active data folder: {status.root}  [{status.label}]")
            print(f"free: {status.to_dict()['free_gib']} GiB of {status.to_dict()['total_gib']} GiB")
            return _OK
        return _show_unavailable(status)

    status = adopt_root(target, label=args.label or "")
    print(f"data folder set to: {status.root}")
    print(f"label: {status.label}   id: {status.lake_id[:8]}")
    print(f"free:  {status.to_dict()['free_gib']} GiB")
    print("\nThis folder is now found by identity, so it keeps working if the drive "
          "remounts at a different path.")
    return _OK


def cmd_auth(args: argparse.Namespace) -> int:
    import os
    import webbrowser

    from .config import KITE_LOGIN_BASE, save_session

    api_key = args.api_key or os.environ.get("KITE_API_KEY") or ""
    api_secret = args.api_secret or os.environ.get("KITE_API_SECRET") or ""
    if not api_key:
        api_key = input("Kite api_key: ").strip()
    if not api_key:
        return _die("api_key is required")

    url = f"{KITE_LOGIN_BASE}?api_key={api_key}&v=3"
    print("\n1. Open this URL and log in to Kite:\n")
    print(f"   {url}\n")
    print("2. After login your browser lands on your redirect URL carrying")
    print("   ?request_token=XXXX — paste that token here.\n")
    if not args.no_browser:
        with __import__("contextlib").suppress(Exception):
            webbrowser.open(url)

    request_token = (args.request_token or input("request_token: ")).strip()
    if not request_token:
        return _die("request_token is required")
    if not api_secret:
        import getpass

        api_secret = getpass.getpass("api_secret (not echoed): ").strip()
    if not api_secret:
        return _die("api_secret is required to exchange the request_token")

    try:
        from kiteconnect import KiteConnect
    except ImportError:
        return _die(
            "kiteconnect is not installed",
            hint="pip install kiteconnect  (inside the kitelake venv)",
        )
    try:
        kite = KiteConnect(api_key=api_key)
        data = kite.generate_session(request_token, api_secret=api_secret)
    except Exception as exc:  # the SDK raises many types; all mean "login failed"
        return _die(f"login failed: {exc}", hint="request_tokens are single-use and expire "
                                                 "within minutes — get a fresh one.")

    path = save_session(api_key, data["access_token"], user_id=str(data.get("user_id") or ""))
    print(f"\nlogged in as {data.get('user_id')}; session saved to {path} (mode 0600)")
    print("Access tokens expire every morning — re-run `kitelake auth` when they do.")
    return _OK


def cmd_instruments(args: argparse.Namespace) -> int:
    from .instruments import master_age, sync_instruments

    if args.age_only:
        age = master_age()
        print("never synced" if age is None else f"instrument master is {age:.1f} hours old")
        return _OK
    info = sync_instruments()
    print(f"{info['instruments']:,} instruments -> {info['path']}")
    print(f"indexed into ledger: {info['indexed']:,}   indices: {info['indices']}")
    print("\nby exchange:")
    print(_table([[k, f"{v:,}"] for k, v in info["by_exchange"].items()], ["exchange", "count"]))
    return _OK


def cmd_universe(args: argparse.Namespace) -> int:
    from .universe import PRESETS, preset_counts, resolve_universe

    if args.list or not args.spec:
        try:
            counts = preset_counts()
        except FileNotFoundError:
            counts = {}
        rows = [
            [name, f"{counts.get(name, '?'):,}" if counts else "?", desc]
            for name, desc in PRESETS.items()
        ]
        print(_table(rows, ["preset", "count", "description"]))
        if not counts:
            print("\n(counts unavailable — run `kitelake instruments` first)")
        return _OK

    instruments = resolve_universe(args.spec)
    print(f"{len(instruments):,} instruments matched {args.spec!r}")
    rows = [
        [i.token, i.exchange, i.tradingsymbol, i.instrument_type, i.segment, i.lot_size]
        for i in instruments[: args.limit]
    ]
    print(_table(rows, ["token", "exch", "symbol", "type", "segment", "lot"]))
    if len(instruments) > args.limit:
        print(f"… and {len(instruments) - args.limit:,} more")
    return _OK


def cmd_plan(args: argparse.Namespace) -> int:
    from .universe import estimate_cost, resolve_universe

    frm = _parse_date(args.frm, default_days_ago=182)
    to = _parse_date(args.to, default_days_ago=0)
    rows = []
    for spec in args.spec:
        instruments = resolve_universe(spec)
        cost = estimate_cost(instruments, args.interval, frm, to, rate=args.rate)
        rows.append(
            [
                spec, f"{cost['instruments']:,}", f"{cost['requests']:,}",
                cost["eta_human"], f"{cost['est_gib']:.2f}", f"{cost['est_rows']:,}",
            ]
        )
    print(f"interval={args.interval}  {frm} .. {to}  "
          f"({(to - frm).days + 1} days, {args.rate} req/s)")
    print(_table(rows, ["universe", "instruments", "requests", "ETA", "est GiB", "est rows"]))
    print("\nSize/row estimates are upper bounds: Kite omits candles for minutes with no")
    print("trade, so illiquid instruments store far less than the theoretical maximum.")
    return _OK


def _print_tier_plan(plan: dict[str, Any], *, interval: str) -> None:
    print(f"interval={plan['interval']}  {plan['frm']} .. {plan['to']}  "
          f"({plan['rate']} req/s)\n")
    rows = [
        [
            t["tier"], t["universe"], f"{t['instruments']:,}", f"{t['new_instruments']:,}",
            f"{t['requests_incremental']:,}", t["eta_incremental"],
            f"{t['est_gib_incremental']:.2f}", t["cumulative_eta"], f"{t['cumulative_gib']:.2f}",
        ]
        for t in plan["tiers"]
    ]
    print(_table(rows, ["#", "universe", "total", "new", "requests", "ETA", "GiB",
                        "cum. ETA", "cum. GiB"]))
    print(f"\ntotal: {plan['total_instruments']:,} instruments, "
          f"{plan['total_requests']:,} requests, {plan['total_eta']}, {plan['total_gib']:.2f} GiB")
    print(f"The tiers are nested, so running them costs "
          f"{plan['total_requests']:,} requests — not the {plan['naive_requests']:,} a naive")
    print(f"sum implies. The ledger skips the {plan['requests_saved_by_dedup']:,}-request overlap "
          f"automatically.")
    print("\nRun them in order with:")
    print(f"  kitelake download --tiers --interval {interval} "
          f"--from {plan['frm']} --to {plan['to']}")


def cmd_tiers(args: argparse.Namespace) -> int:
    from .universe import tier_plan

    frm = _parse_date(args.frm, default_days_ago=182)
    to = _parse_date(args.to, default_days_ago=0)
    _print_tier_plan(tier_plan(args.interval, frm, to, rate=args.rate), interval=args.interval)
    return _OK


def cmd_download(args: argparse.Namespace) -> int:
    from .download import download, download_tiers

    frm = _parse_date(args.frm, default_days_ago=182)
    to = _parse_date(args.to, default_days_ago=0)

    if not args.tiers and not args.spec:
        return _die(
            "give a universe, or --tiers to run all three in order",
            hint="e.g.  kitelake download indices --interval minute\n"
                 "      kitelake download --tiers --interval minute",
        )

    def show(event: dict[str, Any]) -> None:
        kind = event.get("event")
        if kind == "tier_start":
            print(f"\n=== tier {event['tier']}/{event['of']}: {event['universe']} ===")
        elif kind == "tier_end":
            print(f"\n  tier {event['tier']} ({event['universe']}) done: "
                  f"{event['done']:,} chunks, {event['rows']:,} bars "
                  f"({event['already_done']:,} already covered by an earlier tier)")
        elif kind == "tier_abort":
            print(f"\n  tier {event['tier']} aborted — stopping the sequence")
        elif kind == "start":
            print(f"run {event['run_id']}: {event['chunks']:,} chunks over "
                  f"{event['instruments']:,} instruments "
                  f"({event['already_done']:,} already done), ETA {event['eta']}")
        elif kind == "progress":
            print(
                f"\r  {event['pct']:5.1f}%  {event['done']:,}/{event['total']:,} chunks  "
                f"{event['rows']:,} bars  {event['rq_s']:.2f} rq/s  "
                f"eta {timedelta(seconds=event['eta_s'])}  {event.get('symbol','')[:18]:18}",
                end="", flush=True,
            )
        elif kind == "interrupt":
            print(f"\n{event['message']}")
        elif kind == "dry_run":
            print(f"would issue {event['requests']:,} requests over "
                  f"{event['instruments']:,} instruments; ETA {event['eta_human']}, "
                  f"about {event['est_gib']:.2f} GiB")

    common = dict(
        oi=args.oi, continuous=args.continuous, concurrency=args.concurrency,
        rate=args.rate, resume=not args.no_resume, retry_failed=args.retry_failed,
        dry_run=args.dry_run,
    )

    if args.tiers:
        rollup = download_tiers(
            args.interval, frm, to, stop_after=args.stop_after, progress=show, **common
        )
        if rollup.get("dry_run"):
            _print_tier_plan(rollup, interval=args.interval)
            print(f"\n{rollup['note']}")
            return _OK
        print("\n" + "=" * 60)
        print(f"tiers {rollup['tiers_completed']}/{rollup['tiers_requested']} completed "
              f"in {rollup['elapsed_human']}")
        print(f"  bars:   {rollup['rows']:,}   requests: {rollup['requests']:,}")
        print(f"  chunks: {rollup['chunks_done']:,} done  {rollup['chunks_empty']:,} empty  "
              f"{rollup['chunks_failed']:,} failed")
        if rollup.get("fatal"):
            print(f"\nABORTED: {str(rollup['fatal']).splitlines()[0]}")
            print(f"\n  {rollup['resume_command']}")
            return _ERR
        if rollup.get("interrupted"):
            print(f"\nInterrupted. Resume with:\n  {rollup['resume_command']}")
        return _OK

    summary = download(args.spec, args.interval, frm, to, progress=show, **common)
    if summary.get("dry_run"):
        print(summary["note"])
        return _OK

    print("\n" + "-" * 60)
    print(f"run {summary['run_id']}  {summary['elapsed_human']}")
    print(f"  chunks: {summary['done']:,} done  {summary['empty']:,} empty  "
          f"{summary['failed']:,} failed  ({summary['chunks_already_done']:,} skipped as done)")
    print(f"  bars:   {summary['rows']:,}   requests: {summary['requests']:,}")
    print(f"  ledger: {summary['ledger']['pct_complete']}% complete "
          f"({summary['ledger']['chunks_remaining']:,} chunks remaining)")
    if summary.get("fatal"):
        print(f"\nABORTED: {summary['fatal'].splitlines()[0]}")
        print(summary["note"])
        print(f"\n  {summary['resume_command']}")
        return _ERR
    if summary.get("interrupted"):
        print(f"\n{summary['note']}\n\n  {summary['resume_command']}")
    elif summary["failed"]:
        print(f"\n{summary['failed']:,} chunks failed. Retry just those with:")
        print(f"  {summary['resume_command']} --retry-failed")
    return _OK


def cmd_status(args: argparse.Namespace) -> int:
    from .instruments import master_age
    from .manifest import Manifest
    from .volume import lake_status

    status = lake_status()
    if not status.available:
        return _show_unavailable(status)
    info = status.to_dict()
    print(f"data folder: {status.root}  [{status.label}]")
    print(f"free space:  {info['free_gib']} GiB of {info['total_gib']} GiB")
    age = master_age()
    print(f"instruments: {'never synced' if age is None else f'{age:.1f}h old'}")
    with Manifest() as man:
        stats = man.stats(args.interval)
        print(f"\ninterval={stats['interval']}")
        print(f"  chunks     {stats['chunks_settled']:,}/{stats['chunks_total']:,} "
              f"({stats['pct_complete']}%)  remaining {stats['chunks_remaining']:,}")
        print(f"  by status  {stats['chunks_by_status']}")
        print(f"  bars       {stats['candles']:,}")
        print(f"  symbols    {stats['symbols']:,}  on disk {stats['gib']} GiB")
        runs = man.runs(5)
    if runs:
        print("\nrecent runs:")
        print(_table(
            [[r["run_id"], r["universe"][:22], r["interval"], r["frm"], r["to_"],
              r["completed"], r["failed"], r["notes"][:12]] for r in runs],
            ["run", "universe", "interval", "from", "to", "done", "failed", "notes"],
        ))
    return _OK


def cmd_verify(args: argparse.Namespace) -> int:
    from .verify import format_report, verify_lake

    print(format_report(verify_lake(args.interval, sample=args.sample, workers=args.workers)))
    return _OK


def cmd_coverage(args: argparse.Namespace) -> int:
    from .universe import resolve_universe
    from .verify import coverage_report

    frm = _parse_date(args.frm, default_days_ago=182)
    to = _parse_date(args.to, default_days_ago=0)
    tokens = [i.token for i in resolve_universe(args.spec)] if args.spec else None
    table = coverage_report(args.interval, frm, to, tokens=tokens)
    if table.num_rows == 0:
        print("no stored instruments matched — nothing downloaded yet?")
        return _OK
    import polars as pl

    frame = pl.from_arrow(table).sort("completeness_pct")
    print(f"coverage {frm} .. {to}  interval={args.interval}  ({table.num_rows:,} instruments)")
    with pl.Config(tbl_rows=args.limit, tbl_width_chars=140):
        print(frame.head(args.limit))
    thin = frame.filter(pl.col("completeness_pct") < 5)
    print(f"\n{len(thin):,} instruments below 5% completeness "
          f"(usually genuinely illiquid, not missing data)")
    return _OK


def cmd_catalog(args: argparse.Namespace) -> int:
    from .catalog import build_catalog, catalog_stats

    info = build_catalog(hot_universe=args.hot, interval=args.interval)
    if info.get("note"):
        print(info["note"])
        return _OK
    print(f"catalog: {info['path']}  ({info.get('catalog_bytes', 0)/2**20:.1f} MiB)")
    print(f"views:   {', '.join(info['views'])}")
    if info.get("hot_rows"):
        print(f"hot table {info['hot_rows']:,} rows from {info['hot_universe']} "
              f"({info['hot_instruments']:,} instruments)")
        print(f"  native {info['hot_seconds']}s vs parquet {info['parquet_seconds']}s "
              f"-> {info['speedup']}x")
    elif info.get("hot_note"):
        print(f"hot table skipped: {info['hot_note']}")
    stats = catalog_stats()
    for interval, detail in stats["intervals"].items():
        if "error" in detail:
            print(f"  {interval}: error {detail['error'][:80]}")
        else:
            print(f"  {interval}: {detail['rows']:,} bars, "
                  f"{detail['instruments']:,} instruments, "
                  f"{detail['first_ts']} .. {detail['last_ts']}")
    return _OK


def cmd_query(args: argparse.Namespace) -> int:
    import polars as pl

    from .reader import sql

    frame = sql(args.query)
    with pl.Config(tbl_rows=args.limit, tbl_width_chars=160):
        print(frame)
    if args.csv:
        frame.write_csv(args.csv)
        print(f"\nwrote {args.csv}")
    return _OK


def cmd_read(args: argparse.Namespace) -> int:
    import polars as pl

    from .reader import read_bars

    frame = read_bars(
        args.symbol, args.interval, _parse_date(args.frm), _parse_date(args.to), raw=args.raw
    )
    if args.tail:
        frame = frame.tail(args.tail)
    with pl.Config(tbl_rows=args.tail or 20, tbl_width_chars=140):
        print(frame)
    print(f"\n{len(frame):,} rows")
    if args.csv:
        frame.write_csv(args.csv)
        print(f"wrote {args.csv}")
    return _OK


def cmd_ticks(args: argparse.Namespace) -> int:
    from .ticks import TickRecorder, aggregate_ticks_to_seconds

    if args.ticks_cmd == "record":
        from .config import load_credentials
        from .universe import resolve_universe

        instruments = resolve_universe(args.spec)
        print(f"recording FULL-mode ticks for {len(instruments):,} instruments")
        print("This captures data from now forward only — Kite has no tick history.")
        recorder = TickRecorder(load_credentials(), [i.token for i in instruments])
        recorder.run()
        return _OK
    day = _parse_date(args.date, default_days_ago=0)
    path = aggregate_ticks_to_seconds(day, args.exchange)
    print(f"second bars -> {path}" if path else "no ticks recorded for that date")
    return _OK


def cmd_repair(args: argparse.Namespace) -> int:
    """Find instruments whose stored rows fall short of what was fetched, and requeue them."""
    from .manifest import Manifest

    with Manifest() as man:
        short = man.shortfall(args.interval, min_missing=args.min_missing)
        if not short:
            print(f"No shortfall detected for interval={args.interval}. "
                  "Stored rows match what the ledger says was fetched.")
            return _OK

        missing = sum(r["missing"] for r in short)
        print(f"{len(short):,} instruments are missing {missing:,} candles that the ledger "
              f"records as fetched.")
        print("This is the signature of a lost write: the chunks are marked done, so a plain")
        print("resume would skip them and the lake would look complete.\n")
        rows = [
            [r["tradingsymbol"] or r["instrument_token"], f"{r['fetched_rows']:,}",
             f"{r['stored_rows']:,}", f"{r['missing']:,}"]
            for r in short[: args.limit]
        ]
        print(_table(rows, ["symbol", "fetched", "on disk", "missing"]))
        if len(short) > args.limit:
            print(f"… and {len(short) - args.limit:,} more")

        if args.dry_run:
            print("\n--dry-run: nothing changed. Re-run without it to requeue these chunks.")
            return _OK

        tokens = [int(r["instrument_token"]) for r in short]
        reset = man.reset_instruments(args.interval, tokens)
        stats = man.stats(args.interval)

    print(f"\nrequeued {reset:,} chunks across {len(tokens):,} instruments")
    print(f"ledger now {stats['pct_complete']}% complete "
          f"({stats['chunks_remaining']:,} chunks to fetch)")
    print("\nThe parquet files are left in place — merge de-duplicates on timestamp, so the")
    print("refetch fills the holes instead of duplicating what survived. Now run:")
    print(f"  kitelake download --tiers --interval {args.interval} --from … --to …")
    return _OK


def cmd_clean(args: argparse.Namespace) -> int:
    from .writer import clean_staging

    info = clean_staging(older_than_seconds=args.older_than)
    print(f"removed {info['removed']} stale staging files "
          f"({info['bytes_freed']/2**20:.1f} MiB)")
    return _OK


# ─── parser ──────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    from . import __version__

    parser = argparse.ArgumentParser(
        prog="kitelake",
        description="Offline market-data lake fed from Zerodha Kite. "
                    "Storage is relocatable; code lives in the Sterling project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""quickstart:
  kitelake root --pick                       choose where data lives (graphical)
  kitelake auth                              log in to Kite (token expires daily)
  kitelake instruments                       sync the instrument master (no auth)
  kitelake plan nse-all --interval minute    see requests / ETA / size first
  kitelake download nse-all --interval minute --from 2026-02-13 --to 2026-08-13
  kitelake verify && kitelake catalog
  kitelake read RELIANCE --tail 5
""",
    )
    parser.add_argument("--version", action="version", version=f"kitelake {__version__}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("root", help="choose/inspect where the data lives")
    p.add_argument("--pick", action="store_true", help="open a graphical folder chooser")
    p.add_argument("--set", metavar="PATH", help="use this folder")
    p.add_argument("--label", help="friendly name for the folder")
    p.add_argument("--list", action="store_true", help="list known folders and volumes")
    p.add_argument("--use", metavar="LAKE_ID", help="switch to a known folder")
    p.add_argument("--forget", metavar="LAKE_ID", help="unregister (data untouched)")
    p.set_defaults(func=cmd_root)

    p = sub.add_parser("auth", help="log in to Kite and store a session")
    p.add_argument("--api-key")
    p.add_argument("--api-secret")
    p.add_argument("--request-token")
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("instruments", help="sync the instrument master")
    p.add_argument("--age-only", action="store_true", help="just report staleness")
    p.set_defaults(func=cmd_instruments)

    p = sub.add_parser("universe", help="list presets or resolve a spec")
    p.add_argument("spec", nargs="?")
    p.add_argument("--list", action="store_true")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_universe)

    p = sub.add_parser("plan", help="estimate requests, ETA and size (no network)")
    p.add_argument("spec", nargs="+")
    p.add_argument("--interval", default="minute")
    p.add_argument("--from", dest="frm")
    p.add_argument("--to")
    p.add_argument("--rate", type=float, default=2.5)
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("tiers", help="cost the three supported universes as nested tiers")
    p.add_argument("--interval", default="minute")
    p.add_argument("--from", dest="frm")
    p.add_argument("--to")
    p.add_argument("--rate", type=float, default=2.5)
    p.set_defaults(func=cmd_tiers)

    p = sub.add_parser("download", help="fetch candles into the lake")
    p.add_argument("spec", nargs="?", help="universe spec; omit when using --tiers")
    p.add_argument("--tiers", action="store_true",
                   help="run indices -> nse-all -> equity-all in order (nested, no extra cost)")
    p.add_argument("--stop-after", metavar="TIER",
                   help="with --tiers, stop after this tier (e.g. nse-all)")
    p.add_argument("--interval", default="minute")
    p.add_argument("--from", dest="frm")
    p.add_argument("--to")
    p.add_argument("--rate", type=float, default=2.5, help="requests/second (cap 3.0)")
    p.add_argument("--concurrency", type=int, default=6)
    p.add_argument("--oi", choices=["auto", "on", "off"], default="auto")
    p.add_argument("--continuous", action="store_true",
                   help="stitch futures history across expiries")
    p.add_argument("--no-resume", action="store_true", help="re-fetch everything")
    p.add_argument("--retry-failed", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("status", help="progress and gaps")
    p.add_argument("--interval", default="minute")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("verify", help="check stored files for corruption")
    p.add_argument("--interval")
    p.add_argument("--sample", type=int)
    p.add_argument("--workers", type=int, default=8)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("coverage", help="per-instrument completeness")
    p.add_argument("spec", nargs="?")
    p.add_argument("--interval", default="minute")
    p.add_argument("--from", dest="frm")
    p.add_argument("--to")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_coverage)

    p = sub.add_parser("catalog", help="build the DuckDB catalog")
    p.add_argument("--hot", metavar="UNIVERSE", help="materialise this universe natively")
    p.add_argument("--interval", default="minute")
    p.set_defaults(func=cmd_catalog)

    p = sub.add_parser("query", help="run SQL against the lake")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--csv")
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("read", help="print one instrument's bars")
    p.add_argument("symbol")
    p.add_argument("--interval", default="minute")
    p.add_argument("--from", dest="frm")
    p.add_argument("--to")
    p.add_argument("--tail", type=int)
    p.add_argument("--raw", action="store_true", help="stored int64 prices")
    p.add_argument("--csv")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("ticks", help="record live ticks / build second bars")
    tsub = p.add_subparsers(dest="ticks_cmd", required=True)
    tr = tsub.add_parser("record", help="stream and store FULL-mode ticks")
    tr.add_argument("spec")
    tr.set_defaults(func=cmd_ticks)
    ta = tsub.add_parser("aggregate", help="tick file -> second bars")
    ta.add_argument("--date")
    ta.add_argument("--exchange", default="NSE")
    ta.set_defaults(func=cmd_ticks)

    p = sub.add_parser(
        "repair", help="requeue instruments whose stored rows fall short of what was fetched"
    )
    p.add_argument("--interval", default="minute")
    p.add_argument("--min-missing", type=int, default=1,
                   help="ignore shortfalls smaller than this (dedup noise)")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_repair)

    p = sub.add_parser("clean", help="remove stale staging files")
    p.add_argument("--older-than", type=float, default=3600)
    p.set_defaults(func=cmd_clean)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return _OK
    return _guarded(args.func, args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
