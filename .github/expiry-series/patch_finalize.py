from pathlib import Path

p = Path('.github/expiry-series/finalize.py')
text = p.read_text()

sig_marker = "once(STRIKES,\n'''    expiry_types: Sequence[ExpiryType] = (),\n    expiry_ranks: Sequence[int] = (0,),"
sig_start = text.find(sig_marker)
if sig_start < 0:
    raise RuntimeError('finalize pick_strikes signature block not found')
sig_end = text.find("\n\nonce(STRIKES,", sig_start + len(sig_marker))
if sig_end < 0:
    raise RuntimeError('finalize pick_strikes signature block end not found')
sig_replacement = '''text = Path(STRIKES).read_text()
needle = "    expiry_types: Sequence[ExpiryType] = (),\\n    expiry_ranks: Sequence[int] = (0,),\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
replacement = "    expiry_types: Sequence[ExpiryType] = (),\\n    expiry_ranks: Sequence[int] = (0,),\\n    expiry_ranks_by_type: Optional[dict] = None,\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
start = text.find("def pick_strikes")
pos = text.find(needle, start)
if pos < 0:
    raise RuntimeError("pick_strikes signature anchor missing")
text = text[:pos] + replacement + text[pos + len(needle):]
Path(STRIKES).write_text(text)'''
text = text[:sig_start] + sig_replacement + text[sig_end:]

call_marker = "once(SCANNER,\n'''                          moneynesses=ordered, expiry_types=expiry_types,"
call_start = text.find(call_marker)
if call_start < 0:
    raise RuntimeError('finalize attach_strikes call block not found')
call_end = text.find("\n\nonce(SCANNER,", call_start + len(call_marker))
if call_end < 0:
    raise RuntimeError('finalize attach_strikes call block end not found')
call_replacement = '''text = Path(SCANNER).read_text()
old = "    picks = pick_strikes(chain, spot=row.spot, direction=row.direction,\\n                         moneynesses=ordered, expiry_types=expiry_types,\\n                         expiry_ranks=expiry_ranks, today=today)"
new = "    picks = pick_strikes(chain, spot=row.spot, direction=row.direction,\\n                         moneynesses=ordered, expiry_types=expiry_types,\\n                         expiry_ranks=expiry_ranks,\\n                         expiry_ranks_by_type=expiry_ranks_by_type, today=today)"
start = text.find("def attach_strikes(")
end = text.find("def option_order_args(", start)
pos = text.find(old, start, end)
if pos < 0:
    raise RuntimeError("attach_strikes picker call anchor missing")
text = text[:pos] + new + text[pos + len(old):]
Path(SCANNER).write_text(text)'''
text = text[:call_start] + call_replacement + text[call_end:]

p.write_text(text)
print('finalizer anchors scoped')
