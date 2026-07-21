from pathlib import Path

p = Path('.github/expiry-series/apply.py')
text = p.read_text()
start_marker = "once(STRIKES,\n'''    moneynesses: Sequence[Moneyness], min_dte: int = 0,\n    expiry_types: Sequence[ExpiryType] = (),\n    today: Optional[date] = None,\n) -> List[tuple]:''',"
start = text.find(start_marker)
if start < 0:
    raise RuntimeError('pick_strikes apply block not found')
end = text.find("\n\nonce(STRIKES,", start + len(start_marker))
if end < 0:
    raise RuntimeError('pick_strikes apply block end not found')
replacement = '''text = Path(STRIKES).read_text()
needle = "    moneynesses: Sequence[Moneyness], min_dte: int = 0,\\n    expiry_types: Sequence[ExpiryType] = (),\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
new = "    moneynesses: Sequence[Moneyness], min_dte: int = 0,\\n    expiry_types: Sequence[ExpiryType] = (),\\n    expiry_ranks: Sequence[int] = (0,),\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
fn_start = text.find("def pick_strikes(")
pos = text.find(needle, fn_start)
if pos < 0:
    raise RuntimeError("pick_strikes signature anchor missing")
text = text[:pos] + new + text[pos + len(needle):]
Path(STRIKES).write_text(text)'''
p.write_text(text[:start] + replacement + text[end:])
print('base patch anchor scoped to pick_strikes')
