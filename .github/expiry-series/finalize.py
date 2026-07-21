from pathlib import Path


def once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


STRIKES = "backend/app/services/kite_engine/strikes.py"
SCANNER = "backend/app/services/kite_engine/scanner.py"
SERVICE = "backend/app/services/kite_engine/service.py"
SCHEMAS = "backend/app/engines/sterling_kite_engine/schemas.py"
TYPES = "frontend/src/types/kiteEngine.ts"
PANE = "frontend/src/components/kite/SterlingKiteEnginePane.tsx"
TEST = "backend/tests/engines/sterling_kite_engine/test_strikes.py"

# Root cause fix: expiry classification must not assume Thursday. NSE expiries moved
# to Tuesday, and holidays can shift either weekly or monthly expiries earlier. Classify
# from the actual chain: the latest expiry present in each calendar month is monthly;
# earlier expiries in that same month are weekly. A stock chain with one expiry/month is
# therefore monthly-only automatically.
text = Path(STRIKES).read_text()
start = text.index("def _expiry_date_set(")
end = text.index("\n\ndef _filter_chain_by_expiry", start)
new_fn = '''def _expiry_date_set(chain: Sequence[dict], today: date) -> dict:
    """Classify actual chain expiries without assuming a weekday.

    Exchange expiry weekdays change and holidays shift expiries. The instrument dump is
    authoritative: the latest listed expiry in each calendar month is the monthly series;
    any earlier listed expiries in that month are weekly series. This also handles stock
    options correctly because they normally expose only monthly expiries.
    """
    from collections import defaultdict
    from datetime import date as _date

    by_month: dict[tuple[int, int], set[_date]] = defaultdict(set)
    for r in chain:
        raw = str(r.get("expiry_date", "") or r.get("expiry", ""))[:10]
        try:
            d = _date.fromisoformat(raw)
        except (ValueError, TypeError):
            continue
        if d >= today:
            by_month[(d.year, d.month)].add(d)

    out: dict[str, set[str]] = {}
    for dates in by_month.values():
        monthly = max(dates)
        for d in dates:
            out[d.isoformat()] = {"monthly"} if d == monthly else {"weekly"}
    return out
'''
Path(STRIKES).write_text(text[:start] + new_fn + text[end:])

# Support different selected ranks for weekly and monthly. Backwards-compatible callers
# can still pass expiry_ranks; the new mapping is authoritative when supplied.
once(STRIKES,
'''    expiry_types: Sequence[ExpiryType] = (),
    expiry_ranks: Sequence[int] = (0,),
    today: Optional[date] = None,
) -> List[tuple]:''',
'''    expiry_types: Sequence[ExpiryType] = (),
    expiry_ranks: Sequence[int] = (0,),
    expiry_ranks_by_type: Optional[dict] = None,
    today: Optional[date] = None,
) -> List[tuple]:''')

once(STRIKES,
'''    ranks = tuple(sorted({max(0, int(r)) for r in (expiry_ranks or (0,))}))
    for expiry_rank in ranks:
        for m in moneynesses:
            pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,
                               min_dte=min_dte, expiry_types=expiry_types,
                               expiry_rank=expiry_rank, today=today)
            if pick and pick.option_symbol not in seen:
                seen.add(pick.option_symbol)
                out.append((m, pick))
''',
'''    if expiry_ranks_by_type:
        plans = [
            (etype, rank)
            for etype in ("weekly", "monthly")
            if etype in set(expiry_types or ("weekly", "monthly"))
            for rank in sorted({max(0, int(r)) for r in expiry_ranks_by_type.get(etype, ())})
        ]
    else:
        plans = [(None, rank) for rank in sorted({max(0, int(r)) for r in (expiry_ranks or (0,))})]
    for etype, expiry_rank in plans:
        selected_types = [etype] if etype else expiry_types
        for m in moneynesses:
            pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,
                               min_dte=min_dte, expiry_types=selected_types,
                               expiry_rank=expiry_rank, today=today)
            if pick and pick.option_symbol not in seen:
                seen.add(pick.option_symbol)
                out.append((m, pick))
''')

# Second occurrence is pick_contracts.
text = Path(STRIKES).read_text()
needle = '''    expiry_types: Sequence[ExpiryType] = (),
    expiry_ranks: Sequence[int] = (0,),
    today: Optional[date] = None,
) -> List[tuple]:'''
pos = text.find(needle, text.find("def pick_contracts"))
if pos < 0:
    raise RuntimeError("pick_contracts signature anchor missing")
text = text[:pos] + needle.replace("    today:", "    expiry_ranks_by_type: Optional[dict] = None,\n    today:") + text[pos + len(needle):]
Path(STRIKES).write_text(text)

text = Path(STRIKES).read_text()
start = text.index("    ranks = tuple(sorted", text.index("def pick_contracts"))
end = text.index("    return out", start)
old_block = text[start:end]
new_block = '''    if expiry_ranks_by_type:
        plans = [
            (etype, rank)
            for etype in ("weekly", "monthly")
            if etype in set(expiry_types or ("weekly", "monthly"))
            for rank in sorted({max(0, int(r)) for r in expiry_ranks_by_type.get(etype, ())})
        ]
    else:
        plans = [(None, rank) for rank in sorted({max(0, int(r)) for r in (expiry_ranks or (0,))})]
    for etype, expiry_rank in plans:
        selected_types = [etype] if etype else expiry_types
        for m in moneynesses:
            for direction in ("long", "short"):
                pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,
                                   min_dte=min_dte, expiry_types=selected_types,
                                   expiry_rank=expiry_rank, today=today)
                if pick and pick.option_symbol not in seen:
                    seen.add(pick.option_symbol)
                    out.append((m, pick))
'''
Path(STRIKES).write_text(text[:start] + new_block + text[end:])

# Scanner mapping plumbing.
once(SCANNER,
'''    expiry_types: Sequence[ExpiryType] = (),
    expiry_ranks: Sequence[int] = (0,),
) -> EngineSignalRow:''',
'''    expiry_types: Sequence[ExpiryType] = (),
    expiry_ranks: Sequence[int] = (0,),
    expiry_ranks_by_type: Optional[dict] = None,
) -> EngineSignalRow:''')
once(SCANNER,
'''                          moneynesses=ordered, expiry_types=expiry_types,
                          expiry_ranks=expiry_ranks, today=today)''',
'''                          moneynesses=ordered, expiry_types=expiry_types,
                          expiry_ranks=expiry_ranks,
                          expiry_ranks_by_type=expiry_ranks_by_type, today=today)''')
once(SCANNER,
'''        expiry_ranks_indices: Optional[Sequence[int]] = None,
        expiry_ranks_stocks: Optional[Sequence[int]] = None,
        place_cb: Optional[PlaceCb] = None,''',
'''        expiry_ranks_indices: Optional[Sequence[int]] = None,
        expiry_ranks_stocks: Optional[Sequence[int]] = None,
        expiry_series_indices: Optional[dict] = None,
        expiry_series_stocks: Optional[dict] = None,
        place_cb: Optional[PlaceCb] = None,''')

# Spot attach call.
once(SCANNER,
'''                                   expiry_types=_expiry, expiry_ranks=_expiry_ranks)''',
'''                                   expiry_types=_expiry, expiry_ranks=_expiry_ranks,
                                   expiry_ranks_by_type=(expiry_series_indices if item.is_index else expiry_series_stocks))''')

# Derivatives and confluence picker calls.
once(SCANNER,
'''                                           expiry_types=_expiry, expiry_ranks=tuple(_expiry_ranks or (0,)), today=today)''',
'''                                           expiry_types=_expiry, expiry_ranks=tuple(_expiry_ranks or (0,)),
                                           expiry_ranks_by_type=(expiry_series_indices if item.is_index else expiry_series_stocks),
                                           today=today)''')
once(SCANNER,
'''                                          expiry_ranks=tuple(_expiry_ranks or (0,)), today=today)''',
'''                                          expiry_ranks=tuple(_expiry_ranks or (0,)),
                                          expiry_ranks_by_type=(expiry_series_indices if item.is_index else expiry_series_stocks),
                                          today=today)''')

# Config: keep legacy arrays for compatibility, add explicit weekly/monthly selectors.
once(SCHEMAS,
'''    scan_expiry_series_indices: List[int] = [0]
    scan_expiry_series_stocks: List[int] = [0]
''',
'''    scan_expiry_series_indices: List[int] = [0]
    scan_expiry_series_stocks: List[int] = [0]
    # Explicit upcoming series. Weekly: current + next three. Monthly: current + next.
    scan_weekly_series_indices: List[int] = [0, 1, 2, 3]
    scan_monthly_series_indices: List[int] = [0, 1]
    scan_weekly_series_stocks: List[int] = [0, 1, 2, 3]
    scan_monthly_series_stocks: List[int] = [0, 1]
''')
once(SCHEMAS,
'''    @field_validator("scan_expiry_series_indices", "scan_expiry_series_stocks")''',
'''    @field_validator(
        "scan_expiry_series_indices", "scan_expiry_series_stocks",
        "scan_weekly_series_indices", "scan_monthly_series_indices",
        "scan_weekly_series_stocks", "scan_monthly_series_stocks",
    )''')

# Service sends independent maps.
once(SERVICE,
'''            expiry_ranks_indices=cfg_model.scan_expiry_series_indices,
            expiry_ranks_stocks=cfg_model.scan_expiry_series_stocks,
            place_cb=place_cb,''',
'''            expiry_ranks_indices=cfg_model.scan_expiry_series_indices,
            expiry_ranks_stocks=cfg_model.scan_expiry_series_stocks,
            expiry_series_indices={
                "weekly": cfg_model.scan_weekly_series_indices,
                "monthly": cfg_model.scan_monthly_series_indices,
            },
            expiry_series_stocks={
                "weekly": cfg_model.scan_weekly_series_stocks,
                "monthly": cfg_model.scan_monthly_series_stocks,
            },
            place_cb=place_cb,''')

# Frontend config types.
once(TYPES,
'''  scan_expiry_series_indices: number[]; // 0=nearest, 1=next, 2=third
  scan_expiry_series_stocks: number[];
''',
'''  scan_expiry_series_indices: number[]; // legacy compatibility
  scan_expiry_series_stocks: number[];
  scan_weekly_series_indices: number[];
  scan_monthly_series_indices: number[];
  scan_weekly_series_stocks: number[];
  scan_monthly_series_stocks: number[];
''')

# Replace generic Near/Next/Third controls with W1-W4 and M1-M2 controls.
once(PANE,
'''const EXPIRY_SERIES_OPTS = [
  { value: '0', label: 'Near', hint: 'Nearest upcoming expiry of each selected type.' },
  { value: '1', label: 'Next', hint: 'Second upcoming weekly/monthly expiry; reduces near-expiry theta pressure.' },
  { value: '2', label: 'Third', hint: 'Third upcoming weekly/monthly expiry.' },
];''',
'''const WEEKLY_SERIES_OPTS = [0, 1, 2, 3].map((rank) => ({
  value: String(rank), label: `W${rank + 1}`,
  hint: rank === 0 ? 'Current/nearest weekly expiry.' : `${rank + 1}th upcoming weekly expiry.`,
}));
const MONTHLY_SERIES_OPTS = [0, 1].map((rank) => ({
  value: String(rank), label: rank === 0 ? 'M1 Current' : 'M2 Next',
  hint: rank === 0 ? 'Current/nearest monthly expiry.' : 'Next-month expiry to reduce near-expiry theta pressure.',
}));''')

once(PANE,
'''  const toggleExpirySeries = (kind: 'indices' | 'stocks', rank: number) => {
    if (!cfg) return;
    const key = kind === 'indices' ? 'scan_expiry_series_indices' : 'scan_expiry_series_stocks';
    const cur = (cfg[key] ?? [0]) as number[];
    const next = cur.includes(rank) ? cur.filter((x) => x !== rank) : [...cur, rank];
    const finalNext = (next.length ? next : [0]).sort((a, b) => a - b);
    patch({ [key]: finalNext } as Partial<EngineConfigModel>, `${kind === 'indices' ? 'Index' : 'Stock'} expiry series updated`, true);
  };''',
'''  const toggleExpirySeries = (kind: 'indices' | 'stocks', type: 'weekly' | 'monthly', rank: number) => {
    if (!cfg) return;
    const key = `scan_${type}_series_${kind}` as keyof EngineConfigModel;
    const defaults = type === 'weekly' ? [0, 1, 2, 3] : [0, 1];
    const cur = ((cfg[key] as number[] | undefined) ?? defaults);
    const next = cur.includes(rank) ? cur.filter((x) => x !== rank) : [...cur, rank];
    const finalNext = (next.length ? next : [0]).sort((a, b) => a - b);
    patch({ [key]: finalNext } as Partial<EngineConfigModel>, `${kind === 'indices' ? 'Index' : 'Stock'} ${type} series updated`, true);
  };''')

old = '''            <SettingRow label="Idx series" hint="Choose which upcoming weekly/monthly series to use. Near/Next/Third are applied independently to every selected expiry type.">
              <Segmented
                options={EXPIRY_SERIES_OPTS}
                isActive={(v) => (cfg.scan_expiry_series_indices ?? [0]).includes(Number(v))}
                onSelect={(v) => toggleExpirySeries('indices', Number(v))}
              />
            </SettingRow>'''
new = '''            {(cfg.scan_expiries_indices ?? cfg.scan_expiries ?? ['weekly', 'monthly']).includes('weekly') && (
              <SettingRow label="Idx weeks" hint="Current weekly plus the next three. Only contracts actually listed by the exchange are resolved.">
                <Segmented options={WEEKLY_SERIES_OPTS}
                  isActive={(v) => (cfg.scan_weekly_series_indices ?? [0,1,2,3]).includes(Number(v))}
                  onSelect={(v) => toggleExpirySeries('indices', 'weekly', Number(v))} />
              </SettingRow>
            )}
            {(cfg.scan_expiries_indices ?? cfg.scan_expiries ?? ['weekly', 'monthly']).includes('monthly') && (
              <SettingRow label="Idx months" hint="Current month and next month. Select M2 to avoid near-expiry theta decay.">
                <Segmented options={MONTHLY_SERIES_OPTS}
                  isActive={(v) => (cfg.scan_monthly_series_indices ?? [0,1]).includes(Number(v))}
                  onSelect={(v) => toggleExpirySeries('indices', 'monthly', Number(v))} />
              </SettingRow>
            )}'''
once(PANE, old, new)

old = '''            <SettingRow label="Stk series" hint="Choose nearest, next, or third upcoming expiry for stock options.">
              <Segmented
                options={EXPIRY_SERIES_OPTS}
                isActive={(v) => (cfg.scan_expiry_series_stocks ?? [0]).includes(Number(v))}
                onSelect={(v) => toggleExpirySeries('stocks', Number(v))}
              />
            </SettingRow>'''
new = '''            {(cfg.scan_expiries_stocks ?? ['monthly']).includes('weekly') && (
              <SettingRow label="Stk weeks" hint="Current weekly plus the next three, when the exchange lists weekly stock options.">
                <Segmented options={WEEKLY_SERIES_OPTS}
                  isActive={(v) => (cfg.scan_weekly_series_stocks ?? [0,1,2,3]).includes(Number(v))}
                  onSelect={(v) => toggleExpirySeries('stocks', 'weekly', Number(v))} />
              </SettingRow>
            )}
            {(cfg.scan_expiries_stocks ?? ['monthly']).includes('monthly') && (
              <SettingRow label="Stk months" hint="Current month and next month for stock options.">
                <Segmented options={MONTHLY_SERIES_OPTS}
                  isActive={(v) => (cfg.scan_monthly_series_stocks ?? [0,1]).includes(Number(v))}
                  onSelect={(v) => toggleExpirySeries('stocks', 'monthly', Number(v))} />
              </SettingRow>
            )}'''
once(PANE, old, new)

# Clearer empty state: this is resolution/filtering, not a quote-liquidity verdict.
once(PANE,
'''no contract resolved for the selected strike / expiry series''',
'''no listed contract matched the selected strike and expiry series''')

# Tests for Tuesday expiries, type-independent ranks, and requested horizons.
extra = r'''


def test_expiry_classifier_is_weekday_agnostic_and_marks_latest_date_monthly():
    from datetime import date
    from app.services.kite_engine.strikes import _expiry_date_set
    chain = []
    for expiry in ("2026-07-21", "2026-07-28", "2026-08-04", "2026-08-25"):
        chain += _chain([100], "call", expiry=expiry, dte=1)
    labels = _expiry_date_set(chain, date(2026, 7, 1))
    assert labels["2026-07-21"] == {"weekly"}
    assert labels["2026-07-28"] == {"monthly"}
    assert labels["2026-08-04"] == {"weekly"}
    assert labels["2026-08-25"] == {"monthly"}


def test_series_mapping_resolves_four_weeklies_and_two_monthlies_independently():
    from datetime import date
    from app.services.kite_engine.strikes import pick_contracts
    chain = []
    expiries = [
        ("2026-07-21", 1), ("2026-07-28", 8),
        ("2026-08-04", 15), ("2026-08-11", 22), ("2026-08-18", 29), ("2026-08-25", 36),
    ]
    for expiry, dte in expiries:
        chain += _chain([90, 100, 110], "call", expiry=expiry, dte=dte)
        chain += _chain([90, 100, 110], "put", expiry=expiry, dte=dte)
    picks = pick_contracts(
        chain, spot=100, moneynesses=["ATM"], expiry_types=["weekly", "monthly"],
        expiry_ranks_by_type={"weekly": [0, 1, 2, 3], "monthly": [0, 1]},
        today=date(2026, 7, 1),
    )
    expiries_found = {p.expiry for _, p in picks}
    assert expiries_found == {
        "2026-07-21", "2026-08-04", "2026-08-11", "2026-08-18",
        "2026-07-28", "2026-08-25",
    }
    assert len(picks) == 12  # 6 expiries × CE/PE
'''
text = Path(TEST).read_text()
if "test_expiry_classifier_is_weekday_agnostic" not in text:
    Path(TEST).write_text(text.rstrip() + extra + "\n")

print("final expiry-series design applied")
