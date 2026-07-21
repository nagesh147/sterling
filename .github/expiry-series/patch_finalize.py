from pathlib import Path
import re

p = Path('.github/expiry-series/finalize.py')
text = p.read_text()

sig_pattern = re.compile(
    r"once\(STRIKES,\n'''\s*expiry_types: Sequence\[ExpiryType\] = \(\),\n"
    r"\s*expiry_ranks: Sequence\[int\] = \(0,\),\n"
    r"\s*today: Optional\[date\] = None,\n\s*\) -> List\[tuple\]:''',\n"
    r"'''\s*expiry_types: Sequence\[ExpiryType\] = \(\),\n"
    r"\s*expiry_ranks: Sequence\[int\] = \(0,\),\n"
    r"\s*expiry_ranks_by_type: Optional\[dict\] = None,\n"
    r"\s*today: Optional\[date\] = None,\n\s*\) -> List\[tuple\]:'''\)",
    re.S,
)
sig_replacement = '''text = Path(STRIKES).read_text()
needle = "    expiry_types: Sequence[ExpiryType] = (),\\n    expiry_ranks: Sequence[int] = (0,),\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
replacement = "    expiry_types: Sequence[ExpiryType] = (),\\n    expiry_ranks: Sequence[int] = (0,),\\n    expiry_ranks_by_type: Optional[dict] = None,\\n    today: Optional[date] = None,\\n) -> List[tuple]:"
start = text.find("def pick_strikes")
pos = text.find(needle, start)
if pos < 0:
    raise RuntimeError("pick_strikes signature anchor missing")
text = text[:pos] + replacement + text[pos + len(needle):]
Path(STRIKES).write_text(text)'''
text, count = sig_pattern.subn(sig_replacement, text, count=1)
if count != 1:
    raise RuntimeError(f'finalize pick_strikes signature regex matched {count}')

call_pattern = re.compile(
    r"once\(SCANNER,\n'''\s*moneynesses=ordered, expiry_types=expiry_types,\n"
    r"\s*expiry_ranks=expiry_ranks, today=today\)''',\n"
    r"'''\s*moneynesses=ordered, expiry_types=expiry_types,\n"
    r"\s*expiry_ranks=expiry_ranks,\n"
    r"\s*expiry_ranks_by_type=expiry_ranks_by_type, today=today\)'''\)",
    re.S,
)
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
text, count = call_pattern.subn(call_replacement, text, count=1)
if count != 1:
    raise RuntimeError(f'finalize attach_strikes call regex matched {count}')

p.write_text(text)
print('finalizer anchors scoped')
