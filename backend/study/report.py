"""Report generator for the derivatives edge study.

Consumes the result DataFrames from the sweep + robustness + gate audit
stages and produces:
  - DERIVATIVES_EDGE_STUDY.md  (markdown report)
  - derivatives_study_results.csv (full grid)
  - derivatives_study_survivors.csv (gated survivors)
  - derivatives_gate_overfilter.csv (IVR routing sweep)

Pure text/CSV generation — no I/O beyond file writing.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import pandas as pd


def _top_n(survivors: pd.DataFrame, n: int = 10) -> str:
    """Format top-N survivors as markdown table rows."""
    if survivors.empty:
        return "*(none survived the robustness gate)*\n"
    lines = [
        "| # | Config | Trades | Ret% | PF | Sharpe | OOS Sharpe | Keep | P(Loss)% |",
        "|---|--------|--------|------|----|--------|------------|------|----------|",
    ]
    for rank, (_, row) in enumerate(survivors.head(n).iterrows(), 1):
        cfg = f"{row.get('strategy','')}/{row.get('symbol','')[:3]}/{row.get('tf','')}/{row.get('direction','')}/{row.get('instrument','')}"
        lines.append(
            f"| {rank} | {cfg} | {int(row.get('trades',0))} | "
            f"{row.get('ret%','0')}% | {row.get('pf','-')} | "
            f"{row.get('sharpe','0')} | {row.get('oos_sharpe','0')} | "
            f"{row.get('oos_keep','-')} | {row.get('P_loss%','0')}% |"
        )
    return "\n".join(lines) + "\n"


def _futures_vs_options_verdict(survivors: pd.DataFrame) -> str:
    """The key verdict: does options ever beat futures, and when?"""
    if survivors.empty:
        return ("**No configs survived the robustness gate** — the study did not "
                "find a validated edge in either instrument class at the default "
                "thresholds.\n")
    fut = survivors[survivors.get("instrument") == "futures"]
    opt = survivors[~survivors.index.isin(fut.index)] if not fut.empty else survivors

    if fut.empty:
        return ("**Only options configs survived** — but remember options returns "
                "are modeled (calibrated to a single live snapshot), not real. "
                "Treat with appropriate skepticism.\n")
    if len(opt) == 0 or opt.empty:
        return ("**Futures dominate.** No options config cleared the OOS gate. "
                "This is the honest result for the current data window: direction "
                "priced through a fixed vol surface does not beat simple futures SL/TP. "
                "The options verdict may change once a genuine historical IV series "
                "accrues from the forward recorder.\n")

    fut_best = fut.iloc[0] if not fut.empty else None
    opt_best = opt.iloc[0]
    lines = [
        "**Mixed verdict:** both futures and options configs survived.\n",
        f"- Best futures: {fut_best.get('oos_sharpe',0)} OOS Sharpe" if fut_best is not None else "",
        f"- Best options:  {opt_best.get('oos_sharpe',0)} OOS Sharpe (modeled)",
        "",
        "The options verdict is labelled **modeled, calibrated to live surface** — ",
        "vol-*timing* (IV percentile over years) cannot be backtested until the forward ",
        "IV recorder has accrued real historical data.\n",
    ]
    return "".join(lines)


def _gate_audit_summary(gate_df: pd.DataFrame) -> str:
    """Summarize the routing-gate audit sweep."""
    if gate_df.empty:
        return "*(no gate audit data — study may not have completed the audit stage)*\n"
    total = len(gate_df)
    options_routed = int((gate_df["verdict"] == "options").sum())
    futures_routed = int((gate_df["verdict"] == "futures").sum())
    errors = int((gate_df["verdict"] == "ERROR").sum())
    lines = [
        f"- Total IVR-level tests: {total}",
        f"- Routed to options: {options_routed} ({100*options_routed/max(1,total):.0f}%)",
        f"- Routed to futures: {futures_routed} ({100*futures_routed/max(1,total):.0f}%)",
    ]
    if errors:
        lines.append(f"- Errors: {errors}")
    by_ivr = gate_df.groupby("ivr_pct")["verdict"].value_counts().unstack(fill_value=0)
    if not by_ivr.empty and "options" in by_ivr.columns:
        lines.append("")
        lines.append("**Options routing rate by IVR:**")
        for ivr in sorted(by_ivr.index):
            opts = by_ivr.loc[ivr].get("options", 0)
            total_ivr = by_ivr.loc[ivr].sum()
            lines.append(f"  - IVR {ivr}%: {opts}/{total_ivr} options")
    return "\n".join(lines) + "\n"


def _rollup(survivors: pd.DataFrame, col: str) -> str:
    """Per-category rollup table."""
    if survivors.empty or col not in survivors.columns:
        return ""
    groups = survivors.groupby(col).agg(
        count=("trades", "count"),
        best_oos=("oos_sharpe", "max"),
    ).sort_values("best_oos", ascending=False)
    lines = [f"\n### By {col}\n"]
    lines.append("| {col} | Count | Best OOS Sharpe |".format(col=col))
    lines.append("|-------|-------|-----------------|")
    for name, row in groups.iterrows():
        lines.append(f"| {name} | {int(row['count'])} | {row['best_oos']} |")
    return "\n".join(lines) + "\n"


_METHOD_OPTIONS_NOTE = {
    1: "Options results are **modeled** (BSM, calibrated to a single live surface snapshot).",
    2: "Options results are priced through **real recorded IV** from the forward recorder, "
       "over the forward window the recorder has covered so far.",
}


def generate_report(
    results: pd.DataFrame,
    survivors: pd.DataFrame,
    gate_audit: pd.DataFrame,
    snapshots: dict[str, object] | None = None,
    output_dir: str = ".",
    validation_method: int = 1,
) -> str:
    """Generate the DERIVATIVES_EDGE_STUDY.md report + CSVs.

    Returns the path to the generated markdown file.
    """
    now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    snapshot_ts = "no live snapshot"
    if snapshots:
        dates = {s.snapshot_date for s in snapshots.values() if s}
        if dates:
            snapshot_ts = ", ".join(sorted(dates))

    n_total = len(results)
    n_surv = len(survivors)
    pct = round(100 * n_surv / max(1, n_total), 1)

    lines = [
        f"# Derivatives Edge Study",
        f"",
        f"Generated: {now}",
        f"Surface snapshot: {snapshot_ts}",
        f"",
        f"## Summary",
        f"",
        f"- **{n_surv}** of **{n_total}** configs survive the robustness gate ({pct}%)",
        f"- Gate: net return > 0, OOS Sharpe > 0, Monte Carlo p(loss) ≤ 35%",
        f"- Validation method: **{validation_method}** "
        f"({'real-only / forward' if validation_method == 2 else 'calibrate-to-live'})",
        f"- {_METHOD_OPTIONS_NOTE.get(validation_method, _METHOD_OPTIONS_NOTE[1])}",
        f"",
        f"## Futures vs Options",
        f"",
        _futures_vs_options_verdict(survivors),
        f"",
        f"## Top Survivors (by OOS Sharpe)",
        f"",
        _top_n(survivors, n=10),
        f"",
        f"## Gate Over-Filter Audit",
        f"",
        _gate_audit_summary(gate_audit),
    ]

    # Per-category rollups
    for col in ["strategy", "symbol", "tf", "direction", "instrument"]:
        if col in survivors.columns:
            lines.append(_rollup(survivors, col))

    lines.extend([
        "",
        "## Caveats",
        "",
        "- **Options P&L is modeled** (constant-IV BSM, calibrated to a single live surface snapshot). "
          "A genuine historical IV series for vol-*timing* does not yet exist — the forward "
          "IV recorder must accrue data before vol-percentile-based strategies can be honestly backtested.",
        "- **Futures P&L is real** (bar-by-bar from actual 1m OHLCV data).",
        "- Sub-15m timeframes confirmed fee-death in prior runs and are excluded.",
        "- The routing gate was replayed against a live surface snapshot — gate behaviour may differ "
          "under different vol regimes.",
        "- CPCV uses N=6 groups, K=2 test groups, embargo=2×hold_bars.",
        "",
        "## Output Files",
        "",
        f"- `{output_dir}/derivatives_study_results.csv` — full Stage A grid",
        f"- `{output_dir}/derivatives_study_survivors.csv` — robustness-gated survivors",
        f"- `{output_dir}/derivatives_gate_overfilter.csv` — IVR routing sweep",
    ])

    report_md = "\n".join(lines)

    # Write outputs
    os.makedirs(output_dir, exist_ok=True)
    md_path = os.path.join(output_dir, "DERIVATIVES_EDGE_STUDY.md")
    with open(md_path, "w") as fh:
        fh.write(report_md)

    results.to_csv(os.path.join(output_dir, "derivatives_study_results.csv"), index=False)
    survivors.to_csv(os.path.join(output_dir, "derivatives_study_survivors.csv"), index=False)
    gate_audit.to_csv(os.path.join(output_dir, "derivatives_gate_overfilter.csv"), index=False)

    return md_path


def generate_characterization_report(
    surfaces: dict[str, object] | None,
    output_dir: str = ".",
) -> str:
    """Validation method 3 — live-snapshot characterization.

    No backtest is run. We capture the live surface and report the measured
    parameters (spot, ATM IV curve, 25Δ skew, VRP, realized vol, spread%) so
    an operator can see exactly what the surface looks like right now. Written
    to DERIVATIVES_EDGE_STUDY.md so the existing report viewer renders it.
    """
    now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    lines = [
        "# Derivatives Surface Characterization",
        "",
        f"Generated: {now}",
        "",
        "**Diagnostic mode (validation method 3)** — the live option surface is "
        "captured and described below. *No trades are simulated.*",
        "",
    ]

    captured = {k: v for k, v in (surfaces or {}).items() if v is not None}
    if not captured:
        lines += [
            "*(no live surface captured — the underlying has no listed options, "
            "the chain was empty, or no live adapter is connected)*",
            "",
        ]
    for sym, s in captured.items():
        skew = s.skew_25d if s.skew_25d is not None else "n/a"
        vrp = s.vrp if s.vrp is not None else "n/a"
        rv = s.realized_vol_30d if s.realized_vol_30d is not None else "n/a"
        lines += [
            f"## {sym}",
            "",
            f"- Snapshot date: {s.snapshot_date}",
            f"- Spot: {s.spot}",
            f"- Regime: {s.regime_label}"
            + (" (provisional)" if s.regime_provisional else ""),
            f"- 25Δ skew (put − call IV): {skew}",
            f"- VRP (ATM IV / realized vol): {vrp}",
            f"- Realized vol (30d): {rv}",
            f"- Median spread%: {s.spread_median_pct}",
            "",
        ]
        if s.atm_iv:
            lines += ["**ATM IV curve (DTE → IV):**", "", "| DTE | ATM IV |", "|-----|--------|"]
            for dte in sorted(s.atm_iv):
                lines.append(f"| {dte} | {round(s.atm_iv[dte], 4)} |")
            lines.append("")

    report_md = "\n".join(lines)
    os.makedirs(output_dir, exist_ok=True)
    md_path = os.path.join(output_dir, "DERIVATIVES_EDGE_STUDY.md")
    with open(md_path, "w") as fh:
        fh.write(report_md)
    return md_path
