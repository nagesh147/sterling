from pathlib import Path

p = Path('.github/expiry-series/finalize.py')
text = p.read_text()

old_sig = "once(STRIKES,\n'''    expiry_types: Sequence[ExpiryType] = (),\n    expiry_ranks: Sequence[int] = (0,),\n    today: Optional[date] = None,\n) -> List[tuple]:''',\n'''    expiry_types: Sequence[ExpiryType] = (),\n    expiry_ranks: Sequence[int] = (0,),\n    expiry_ranks_by_type: Optional[dict] = None,\n    today: Optional[date] = None,\n) -> List[tuple]:''')"
new_sig = '''text = Path(STRIKES).read_text()
needle = "    expiry_types: Sequence[ExpiryType] = (),\\n    expiry_ranks: Sequence[int] = (0,),\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
replacement = "    expiry_types: Sequence[ExpiryType] = (),\\n    expiry_ranks: Sequence[int] = (0,),\\n    expiry_ranks_by_type: Optional[dict] = None,\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
start = text.find("def pick_strikes")
pos = text.find(needle, start)
if pos < 0:
    raise RuntimeError("pick_strikes signature anchor missing")
text = text[:pos] + replacement + text[pos + len(needle):]
Path(STRIKES).write_text(text)'''
if old_sig not in text:
    raise RuntimeError('finalize pick_strikes signature block not found')
text = text.replace(old_sig, new_sig, 1)

old_call = "once(SCANNER,\n'''                          moneynesses=ordered, expiry_types=expiry_types,\n                           expiry_ranks=expiry_ranks, today=today)''',\n'''                          moneynesses=ordered, expiry_types=expiry_types,\n                           expiry_ranks=expiry_ranks,\n                           expiry_ranks_by_type=expiry_ranks_by_type, today=today)''')"
new_call = '''text = Path(SCANNER).read_text()
old = "    picks = pick_strikes(chain, spot=row.spot, direction=row.direction,\\n                         moneynesses=ordered, expiry_types=expiry_types,\\n                         expiry_ranks=expiry_ranks, today=today)"
new = "    picks = pick_strikes(chain, spot=row.spot, direction=row.direction,\\n                         moneynesses=ordered, expiry_types=expiry_types,\\n                         expiry_ranks=expiry_ranks,\\n                         expiry_ranks_by_type=expiry_ranks_by_type, today=today)"
start = text.find("def attach_strikes(")
end = text.find("def option_order_args(", start)
pos = text.find(old, start, end)
if pos < 0:
    raise RuntimeError("attach_strikes picker call anchor missing")
text = text[:pos] + new + text[pos + len(old):]
Path(SCANNER).write_text(text)'''
if old_call not in text:
    raise RuntimeError('finalize attach_strikes call block not found')
text = text.replace(old_call, new_call, 1)

p.write_text(text)
print('finalizer anchors scoped')
