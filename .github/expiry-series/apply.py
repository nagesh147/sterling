from pathlib import Path


def once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{path}: expected one anchor, found {count}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1))

STRIKES='backend/app/services/kite_engine/strikes.py'
SCANNER='backend/app/services/kite_engine/scanner.py'
SERVICE='backend/app/services/kite_engine/service.py'
SCHEMAS='backend/app/engines/sterling_kite_engine/schemas.py'
TYPES='frontend/src/types/kiteEngine.ts'
PANE='frontend/src/components/kite/SterlingKiteEnginePane.tsx'
TEST='backend/tests/engines/sterling_kite_engine/test_strikes.py'

# --- Strike resolver: select 1st/2nd/3rd expiry within each selected type. ---
once(STRIKES,
'''    min_dte: int = 0,
    expiry_types: Sequence[ExpiryType] = (),
    today: Optional[date] = None,
) -> Optional[OptionPick]:''',
'''    min_dte: int = 0,
    expiry_types: Sequence[ExpiryType] = (),
    expiry_rank: int = 0,
    today: Optional[date] = None,
) -> Optional[OptionPick]:''')

once(STRIKES,
'''    # nearest expiry only
    near_dte = min(int(r["dte"]) for r in rows)
    rows = sorted((r for r in rows if int(r["dte"]) == near_dte), key=lambda r: float(r["strike"]))
    strikes = [float(r["strike"]) for r in rows]
''',
'''    # Select the requested upcoming expiry series. Rank 0 = nearest matching expiry,
    # rank 1 = next matching expiry, etc. This is applied after weekly/monthly filtering.
    expiry_dtes = sorted({int(r["dte"]) for r in rows})
    rank = max(0, int(expiry_rank or 0))
    if rank >= len(expiry_dtes):
        return None
    selected_dte = expiry_dtes[rank]
    rows = sorted((r for r in rows if int(r["dte"]) == selected_dte), key=lambda r: float(r["strike"]))
    strikes = [float(r["strike"]) for r in rows]
''')

once(STRIKES,
'''    moneynesses: Sequence[Moneyness], min_dte: int = 0,
    expiry_types: Sequence[ExpiryType] = (),
    today: Optional[date] = None,
) -> List[tuple]:''',
'''    moneynesses: Sequence[Moneyness], min_dte: int = 0,
    expiry_types: Sequence[ExpiryType] = (),
    expiry_ranks: Sequence[int] = (0,),
    today: Optional[date] = None,
) -> List[tuple]:''')

once(STRIKES,
'''    for m in moneynesses:
        pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,
                           min_dte=min_dte, expiry_types=expiry_types, today=today)
        if pick and pick.option_symbol not in seen:
            seen.add(pick.option_symbol)
            out.append((m, pick))
''',
'''    ranks = tuple(sorted({max(0, int(r)) for r in (expiry_ranks or (0,))}))
    for expiry_rank in ranks:
        for m in moneynesses:
            pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,
                               min_dte=min_dte, expiry_types=expiry_types,
                               expiry_rank=expiry_rank, today=today)
            if pick and pick.option_symbol not in seen:
                seen.add(pick.option_symbol)
                out.append((m, pick))
''')

once(STRIKES,
'''    moneynesses: Sequence[Moneyness], min_dte: int = 0,
    expiry_types: Sequence[ExpiryType] = (),
    today: Optional[date] = None,
) -> List[tuple]:
    """Resolve BOTH the CE and the PE contract at each requested moneyness''',
'''    moneynesses: Sequence[Moneyness], min_dte: int = 0,
    expiry_types: Sequence[ExpiryType] = (),
    expiry_ranks: Sequence[int] = (0,),
    today: Optional[date] = None,
) -> List[tuple]:
    """Resolve BOTH the CE and the PE contract at each requested moneyness''')

once(STRIKES,
'''    for m in moneynesses:
        for direction in ("long", "short"):  # long → CE, short → PE
            pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,
                               min_dte=min_dte, expiry_types=expiry_types, today=today)
            if pick and pick.option_symbol not in seen:
                seen.add(pick.option_symbol)
                out.append((m, pick))
''',
'''    ranks = tuple(sorted({max(0, int(r)) for r in (expiry_ranks or (0,))}))
    for expiry_rank in ranks:
        for m in moneynesses:
            for direction in ("long", "short"):  # long → CE, short → PE
                pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,
                                   min_dte=min_dte, expiry_types=expiry_types,
                                   expiry_rank=expiry_rank, today=today)
                if pick and pick.option_symbol not in seen:
                    seen.add(pick.option_symbol)
                    out.append((m, pick))
''')

# --- Scanner wiring. ---
once(SCANNER,
'''    moneynesses: Sequence[str] = ("ATM",), today: Optional[date] = None,
    expiry_types: Sequence[ExpiryType] = (),
) -> EngineSignalRow:''',
'''    moneynesses: Sequence[str] = ("ATM",), today: Optional[date] = None,
    expiry_types: Sequence[ExpiryType] = (),
    expiry_ranks: Sequence[int] = (0,),
) -> EngineSignalRow:''')

once(SCANNER,
'''    picks = pick_strikes(chain, spot=row.spot, direction=row.direction,
                         moneynesses=ordered, expiry_types=expiry_types, today=today)''',
'''    picks = pick_strikes(chain, spot=row.spot, direction=row.direction,
                         moneynesses=ordered, expiry_types=expiry_types,
                         expiry_ranks=expiry_ranks, today=today)''')

once(SCANNER,
'''        expiry_types_indices: Optional[Sequence[ExpiryType]] = None,
        expiry_types_stocks: Optional[Sequence[ExpiryType]] = None,
        place_cb: Optional[PlaceCb] = None,''',
'''        expiry_types_indices: Optional[Sequence[ExpiryType]] = None,
        expiry_types_stocks: Optional[Sequence[ExpiryType]] = None,
        expiry_ranks_indices: Optional[Sequence[int]] = None,
        expiry_ranks_stocks: Optional[Sequence[int]] = None,
        place_cb: Optional[PlaceCb] = None,''')

once(SCANNER,
'''                _expiry = expiry_types_indices if (expiry_types_indices is not None and item.is_index) else expiry_types_stocks if (expiry_types_stocks is not None and not item.is_index) else expiry_types
                
                latest_ts = candles[-1].timestamp_ms''',
'''                _expiry = expiry_types_indices if (expiry_types_indices is not None and item.is_index) else expiry_types_stocks if (expiry_types_stocks is not None and not item.is_index) else expiry_types
                _expiry_ranks = expiry_ranks_indices if item.is_index else expiry_ranks_stocks
                _expiry_ranks = tuple(_expiry_ranks or (0,))
                
                latest_ts = candles[-1].timestamp_ms''')

once(SCANNER,
'''                                   moneynesses=moneyness, today=today,
                                   expiry_types=_expiry)''',
'''                                   moneynesses=moneyness, today=today,
                                   expiry_types=_expiry, expiry_ranks=_expiry_ranks)''')

# There are two later _expiry assignments, one in derivatives and one in confluence.
text = Path(SCANNER).read_text()
needle = '''                _expiry = expiry_types_indices if (expiry_types_indices is not None and item.is_index) else expiry_types_stocks if (expiry_types_stocks is not None and not item.is_index) else expiry_types
                contracts = pick_contracts(chain, spot=spot, moneynesses=moneyness,
                                           expiry_types=_expiry, today=today)'''
replacement = '''                _expiry = expiry_types_indices if (expiry_types_indices is not None and item.is_index) else expiry_types_stocks if (expiry_types_stocks is not None and not item.is_index) else expiry_types
                _expiry_ranks = expiry_ranks_indices if item.is_index else expiry_ranks_stocks
                contracts = pick_contracts(chain, spot=spot, moneynesses=moneyness,
                                           expiry_types=_expiry, expiry_ranks=tuple(_expiry_ranks or (0,)), today=today)'''
if replacement not in text:
    if text.count(needle) != 1: raise RuntimeError('derivatives expiry anchor')
    Path(SCANNER).write_text(text.replace(needle, replacement, 1))

text = Path(SCANNER).read_text()
needle = '''                _expiry = expiry_types_indices if (expiry_types_indices is not None and item.is_index) else expiry_types_stocks if (expiry_types_stocks is not None and not item.is_index) else expiry_types
                chain = chain_rows_for(option_rows, item.tradingsymbol, today)'''
replacement = '''                _expiry = expiry_types_indices if (expiry_types_indices is not None and item.is_index) else expiry_types_stocks if (expiry_types_stocks is not None and not item.is_index) else expiry_types
                _expiry_ranks = expiry_ranks_indices if item.is_index else expiry_ranks_stocks
                chain = chain_rows_for(option_rows, item.tradingsymbol, today)'''
if replacement not in text:
    if text.count(needle) != 1: raise RuntimeError('confluence expiry anchor')
    Path(SCANNER).write_text(text.replace(needle, replacement, 1))

once(SCANNER,
'''                                         moneynesses=ordered, expiry_types=_expiry, today=today)''',
'''                                         moneynesses=ordered, expiry_types=_expiry,
                                         expiry_ranks=tuple(_expiry_ranks or (0,)), today=today)''')

# --- API/config and service wiring. ---
once(SCHEMAS,
'''    scan_expiries_indices: Optional[List[Literal["weekly", "monthly"]]] = None
    scan_expiries_stocks: Optional[List[Literal["weekly", "monthly"]]] = None
''',
'''    scan_expiries_indices: Optional[List[Literal["weekly", "monthly"]]] = None
    scan_expiries_stocks: Optional[List[Literal["weekly", "monthly"]]] = None
    # Upcoming series ranks within each selected type: 0=nearest, 1=next, 2=third.
    # Applied independently to weekly and monthly expiries.
    scan_expiry_series_indices: List[int] = [0]
    scan_expiry_series_stocks: List[int] = [0]
''')

once(SCHEMAS,
'''    @field_validator("target_delta")
''',
'''    @field_validator("scan_expiry_series_indices", "scan_expiry_series_stocks")
    @classmethod
    def _valid_expiry_series(cls, v):
        values = sorted({min(5, max(0, int(x))) for x in (v or [0])})
        return values or [0]

    @field_validator("target_delta")
''')

once(SERVICE,
'''            expiry_types_indices=cfg_model.scan_expiries_indices,
            expiry_types_stocks=cfg_model.scan_expiries_stocks,
            place_cb=place_cb,''',
'''            expiry_types_indices=cfg_model.scan_expiries_indices,
            expiry_types_stocks=cfg_model.scan_expiries_stocks,
            expiry_ranks_indices=cfg_model.scan_expiry_series_indices,
            expiry_ranks_stocks=cfg_model.scan_expiry_series_stocks,
            place_cb=place_cb,''')

# --- Frontend config + controls. ---
once(TYPES,
'''  scan_expiries_indices?: ScanExpiry[] | null;
  scan_expiries_stocks?: ScanExpiry[] | null;
''',
'''  scan_expiries_indices?: ScanExpiry[] | null;
  scan_expiries_stocks?: ScanExpiry[] | null;
  scan_expiry_series_indices: number[]; // 0=nearest, 1=next, 2=third
  scan_expiry_series_stocks: number[];
''')

once(PANE,
'''const EXPIRY_OPTS: { value: ScanExpiry; label: string; hint: string }[] = [
  { value: 'weekly', label: 'Weekly', hint: 'Weekly contracts expiring every Thursday (including current week).' },
  { value: 'monthly', label: 'Monthly', hint: 'Monthly contracts expiring on the last Thursday of the month.' },
];
''',
'''const EXPIRY_OPTS: { value: ScanExpiry; label: string; hint: string }[] = [
  { value: 'weekly', label: 'Weekly', hint: 'Weekly contracts expiring every Thursday.' },
  { value: 'monthly', label: 'Monthly', hint: 'Monthly contracts expiring on the last Thursday of the month.' },
];
const EXPIRY_SERIES_OPTS = [
  { value: '0', label: 'Near', hint: 'Nearest upcoming expiry of each selected type.' },
  { value: '1', label: 'Next', hint: 'Second upcoming weekly/monthly expiry; reduces near-expiry theta pressure.' },
  { value: '2', label: 'Third', hint: 'Third upcoming weekly/monthly expiry.' },
];
''')

once(PANE,
'''  const toggleExpiryStocks = (e: ScanExpiry) => {
    if (!cfg) return;
    const cur = cfg.scan_expiries_stocks ?? ['monthly'];
    const has = cur.includes(e);
    const next = has ? cur.filter((x) => x !== e) : [...cur, e];
    const finalNext = next.length ? next : ['weekly', 'monthly'];
    patch({ scan_expiries_stocks: finalNext as ScanExpiry[] }, `Stocks expiries updated to ${finalNext.join(', ')}`, true);
  };
''',
'''  const toggleExpiryStocks = (e: ScanExpiry) => {
    if (!cfg) return;
    const cur = cfg.scan_expiries_stocks ?? ['monthly'];
    const has = cur.includes(e);
    const next = has ? cur.filter((x) => x !== e) : [...cur, e];
    const finalNext = next.length ? next : ['weekly', 'monthly'];
    patch({ scan_expiries_stocks: finalNext as ScanExpiry[] }, `Stocks expiries updated to ${finalNext.join(', ')}`, true);
  };

  const toggleExpirySeries = (kind: 'indices' | 'stocks', rank: number) => {
    if (!cfg) return;
    const key = kind === 'indices' ? 'scan_expiry_series_indices' : 'scan_expiry_series_stocks';
    const cur = (cfg[key] ?? [0]) as number[];
    const next = cur.includes(rank) ? cur.filter((x) => x !== rank) : [...cur, rank];
    const finalNext = (next.length ? next : [0]).sort((a, b) => a - b);
    patch({ [key]: finalNext } as Partial<EngineConfigModel>, `${kind === 'indices' ? 'Index' : 'Stock'} expiry series updated`, true);
  };
''')

once(PANE,
'''            <SettingRow label="Stk exp." hint="Stock option expiries — stocks default to monthly only.">
              <Segmented
                options={EXPIRY_OPTS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
                isActive={(v) => (cfg.scan_expiries_stocks ?? ['monthly']).includes(v as ScanExpiry)}
                onSelect={(v) => toggleExpiryStocks(v as ScanExpiry)}
              />
            </SettingRow>
''',
'''            <SettingRow label="Idx series" hint="Choose which upcoming weekly/monthly series to use. Near/Next/Third are applied independently to every selected expiry type.">
              <Segmented
                options={EXPIRY_SERIES_OPTS}
                isActive={(v) => (cfg.scan_expiry_series_indices ?? [0]).includes(Number(v))}
                onSelect={(v) => toggleExpirySeries('indices', Number(v))}
              />
            </SettingRow>
            <SettingRow label="Stk exp." hint="Stock option expiry types — stocks default to monthly only.">
              <Segmented
                options={EXPIRY_OPTS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
                isActive={(v) => (cfg.scan_expiries_stocks ?? ['monthly']).includes(v as ScanExpiry)}
                onSelect={(v) => toggleExpiryStocks(v as ScanExpiry)}
              />
            </SettingRow>
            <SettingRow label="Stk series" hint="Choose nearest, next, or third upcoming expiry for stock options.">
              <Segmented
                options={EXPIRY_SERIES_OPTS}
                isActive={(v) => (cfg.scan_expiry_series_stocks ?? [0]).includes(Number(v))}
                onSelect={(v) => toggleExpirySeries('stocks', Number(v))}
              />
            </SettingRow>
''')

once(PANE,
'''          <span style={{ fontSize: 10, color: k.dim }}>no liquid contract at the selected strikes</span>''',
'''          <span style={{ fontSize: 10, color: k.dim }}>no contract resolved for the selected strike / expiry series</span>''')

# --- Focused backend tests. ---
extra = r'''


def test_pick_strike_can_select_next_monthly_expiry():
    from datetime import date
    near = _chain([90, 100, 110], "call", expiry="2026-07-30", dte=9)
    nxt = _chain([90, 100, 110], "call", expiry="2026-08-27", dte=37)
    pick = pick_strike(near + nxt, spot=101, direction="long", moneyness="ATM",
                       expiry_types=["monthly"], expiry_rank=1, today=date(2026, 7, 21))
    assert pick is not None
    assert pick.expiry == "2026-08-27" and pick.strike == 100


def test_pick_contracts_multiple_series_resolves_each_selected_expiry():
    from datetime import date
    from app.services.kite_engine.strikes import pick_contracts
    chain = []
    for expiry, dte in (("2026-07-23", 2), ("2026-07-30", 9), ("2026-08-06", 16)):
        chain += _chain([90, 100, 110], "call", expiry=expiry, dte=dte)
        chain += _chain([90, 100, 110], "put", expiry=expiry, dte=dte)
    picks = pick_contracts(chain, spot=100, moneynesses=["ATM"],
                           expiry_types=["weekly"], expiry_ranks=[0, 1],
                           today=date(2026, 7, 21))
    assert {(p.option_type, p.expiry) for _, p in picks} == {
        ("CE", "2026-07-23"), ("PE", "2026-07-23"),
        ("CE", "2026-07-30"), ("PE", "2026-07-30"),
    }
'''
text = Path(TEST).read_text()
if 'test_pick_strike_can_select_next_monthly_expiry' not in text:
    Path(TEST).write_text(text.rstrip() + extra + '\n')

print('expiry-series selection applied')
