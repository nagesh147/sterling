from pathlib import Path

p = Path('.github/expiry-series/apply.py')
text = p.read_text()

# Replace the ambiguous pick_strikes signature patch with a function-scoped edit.
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

# Scope the first loop rewrite to pick_strikes.
loop_start = text.find("once(STRIKES,\n'''    for m in moneynesses:")
if loop_start < 0:
    raise RuntimeError('pick_strikes loop apply block not found')
loop_end = text.find("\n\nonce(STRIKES,", loop_start + 1)
if loop_end < 0:
    raise RuntimeError('pick_strikes loop apply block end not found')
loop_replacement = '''text = Path(STRIKES).read_text()
fn_start = text.find("def pick_strikes(")
fn_end = text.find("def pick_contracts(", fn_start)
loop_start = text.find("    for m in moneynesses:", fn_start, fn_end)
return_pos = text.find("    return out", loop_start, fn_end)
if loop_start < 0 or return_pos < 0:
    raise RuntimeError("pick_strikes loop anchor missing")
new = "    ranks = tuple(sorted({max(0, int(r)) for r in (expiry_ranks or (0,))}))\\n    for expiry_rank in ranks:\\n        for m in moneynesses:\\n            pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,\\n                               min_dte=min_dte, expiry_types=expiry_types,\\n                               expiry_rank=expiry_rank, today=today)\\n            if pick and pick.option_symbol not in seen:\\n                seen.add(pick.option_symbol)\\n                out.append((m, pick))\\n"
text = text[:loop_start] + new + text[return_pos:]
Path(STRIKES).write_text(text)'''
text = text[:loop_start] + loop_replacement + text[loop_end:]

# Scope the remaining generic signature block to pick_contracts.
contract_sig_start = text.find("once(STRIKES,\n'''    moneynesses: Sequence[Moneyness], min_dte: int = 0,", text.find(loop_replacement) + len(loop_replacement))
if contract_sig_start < 0:
    raise RuntimeError('pick_contracts signature apply block not found')
contract_sig_end = text.find("\n\nonce(STRIKES,", contract_sig_start + 1)
if contract_sig_end < 0:
    raise RuntimeError('pick_contracts signature block end not found')
contract_sig_replacement = '''text = Path(STRIKES).read_text()
fn_start = text.find("def pick_contracts(")
fn_end = text.find("def pick_by_delta(", fn_start)
needle = "    expiry_types: Sequence[ExpiryType] = (),\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
pos = text.find(needle, fn_start, fn_end)
if pos < 0:
    raise RuntimeError("pick_contracts signature anchor missing")
new = "    expiry_types: Sequence[ExpiryType] = (),\\n    expiry_ranks: Sequence[int] = (0,),\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
text = text[:pos] + new + text[pos + len(needle):]
Path(STRIKES).write_text(text)'''
text = text[:contract_sig_start] + contract_sig_replacement + text[contract_sig_end:]

# Scope the remaining loop rewrite to pick_contracts and ignore whitespace variations.
contract_loop_start = text.find("once(STRIKES,\n'''    for m in moneynesses:", text.find(contract_sig_replacement) + len(contract_sig_replacement))
if contract_loop_start < 0:
    raise RuntimeError('pick_contracts loop apply block not found')
contract_loop_end = text.find("\n\n# --- Scanner wiring.", contract_loop_start)
if contract_loop_end < 0:
    raise RuntimeError('pick_contracts loop apply block end not found')
contract_loop_replacement = '''text = Path(STRIKES).read_text()
fn_start = text.find("def pick_contracts(")
fn_end = text.find("def pick_by_delta(", fn_start)
loop_start = text.find("    for m in moneynesses:", fn_start, fn_end)
return_pos = text.find("    return out", loop_start, fn_end)
if loop_start < 0 or return_pos < 0:
    raise RuntimeError("pick_contracts loop anchor missing")
new = "    ranks = tuple(sorted({max(0, int(r)) for r in (expiry_ranks or (0,))}))\\n    for expiry_rank in ranks:\\n        for m in moneynesses:\\n            for direction in (\\\"long\\\", \\\"short\\\"):\\n                pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,\\n                                   min_dte=min_dte, expiry_types=expiry_types,\\n                                   expiry_rank=expiry_rank, today=today)\\n                if pick and pick.option_symbol not in seen:\\n                    seen.add(pick.option_symbol)\\n                    out.append((m, pick))\\n"
text = text[:loop_start] + new + text[return_pos:]
Path(STRIKES).write_text(text)'''
text = text[:contract_loop_start] + contract_loop_replacement + text[contract_loop_end:]

p.write_text(text)
print('base patch anchors scoped to strike resolver functions')
