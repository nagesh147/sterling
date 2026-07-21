from pathlib import Path

p = Path('.github/expiry-series/apply.py')
text = p.read_text()

signature_start = "once(STRIKES,\n'''    moneynesses: Sequence[Moneyness], min_dte: int = 0,\n    expiry_types: Sequence[ExpiryType] = (),\n    today: Optional[date] = None,\n) -> List[tuple]:''',"
start = text.find(signature_start)
if start < 0:
    raise RuntimeError('pick_strikes apply block not found')
end = text.find("\n\nonce(STRIKES,", start + len(signature_start))
if end < 0:
    raise RuntimeError('pick_strikes apply block end not found')
signature_replacement = '''text = Path(STRIKES).read_text()
needle = "    moneynesses: Sequence[Moneyness], min_dte: int = 0,\\n    expiry_types: Sequence[ExpiryType] = (),\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
new = "    moneynesses: Sequence[Moneyness], min_dte: int = 0,\\n    expiry_types: Sequence[ExpiryType] = (),\\n    expiry_ranks: Sequence[int] = (0,),\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
fn_start = text.find("def pick_strikes(")
pos = text.find(needle, fn_start)
if pos < 0:
    raise RuntimeError("pick_strikes signature anchor missing")
text = text[:pos] + new + text[pos + len(needle):]
Path(STRIKES).write_text(text)'''
text = text[:start] + signature_replacement + text[end:]

loop_start = text.find("once(STRIKES,\n'''    for m in moneynesses:")
if loop_start < 0:
    raise RuntimeError('pick_strikes loop apply block not found')
loop_end = text.find("\n\nonce(STRIKES,", loop_start + 1)
if loop_end < 0:
    raise RuntimeError('pick_strikes loop apply block end not found')
loop_replacement = '''text = Path(STRIKES).read_text()
old = "    for m in moneynesses:\\n        pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,\\n                          min_dte=min_dte, expiry_types=expiry_types, today=today)\\n        if pick and pick.option_symbol not in seen:\\n            seen.add(pick.option_symbol)\\n            out.append((m, pick))\\n"
new = "    ranks = tuple(sorted({max(0, int(r)) for r in (expiry_ranks or (0,))}))\\n    for expiry_rank in ranks:\\n        for m in moneynesses:\\n            pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,\\n                               min_dte=min_dte, expiry_types=expiry_types,\\n                               expiry_rank=expiry_rank, today=today)\\n            if pick and pick.option_symbol not in seen:\\n                seen.add(pick.option_symbol)\\n                out.append((m, pick))\\n"
fn_start = text.find("def pick_strikes(")
fn_end = text.find("def pick_contracts(", fn_start)
pos = text.find(old, fn_start, fn_end)
if pos < 0:
    raise RuntimeError("pick_strikes loop anchor missing")
text = text[:pos] + new + text[pos + len(old):]
Path(STRIKES).write_text(text)'''
text = text[:loop_start] + loop_replacement + text[loop_end:]

contract_loop_start = text.find("once(STRIKES,\n'''    for m in moneynesses:", text.find("# --- Scanner wiring."))
if contract_loop_start >= 0:
    raise RuntimeError('unexpected contract loop after scanner marker')
contract_loop_start = text.find("once(STRIKES,\n'''    for m in moneynesses:", loop_start + len(loop_replacement))
if contract_loop_start < 0:
    raise RuntimeError('pick_contracts loop apply block not found')
contract_loop_end = text.find("\n\n# --- Scanner wiring.", contract_loop_start)
if contract_loop_end < 0:
    raise RuntimeError('pick_contracts loop apply block end not found')
contract_loop_replacement = '''text = Path(STRIKES).read_text()
old = "    for m in moneynesses:\\n        for direction in (\\\"long\\\", \\\"short\\\"):  # long → CE, short → PE\\n            pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,\\n                              min_dte=min_dte, expiry_types=expiry_types, today=today)\\n            if pick and pick.option_symbol not in seen:\\n                seen.add(pick.option_symbol)\\n                out.append((m, pick))\\n"
new = "    ranks = tuple(sorted({max(0, int(r)) for r in (expiry_ranks or (0,))}))\\n    for expiry_rank in ranks:\\n        for m in moneynesses:\\n            for direction in (\\\"long\\\", \\\"short\\\"):  # long → CE, short → PE\\n                pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,\\n                                   min_dte=min_dte, expiry_types=expiry_types,\\n                                   expiry_rank=expiry_rank, today=today)\\n                if pick and pick.option_symbol not in seen:\\n                    seen.add(pick.option_symbol)\\n                    out.append((m, pick))\\n"
fn_start = text.find("def pick_contracts(")
fn_end = text.find("def pick_by_delta(", fn_start)
pos = text.find(old, fn_start, fn_end)
if pos < 0:
    raise RuntimeError("pick_contracts loop anchor missing")
text = text[:pos] + new + text[pos + len(old):]
Path(STRIKES).write_text(text)'''
text = text[:contract_loop_start] + contract_loop_replacement + text[contract_loop_end:]

p.write_text(text)
print('base patch anchors scoped to strike resolver functions')
