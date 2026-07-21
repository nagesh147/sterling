from pathlib import Path

p = Path('.github/expiry-series/finalize.py')
text = p.read_text()
old = '''once(STRIKES,
''' + "'''    expiry_types: Sequence[ExpiryType] = (),\n    expiry_ranks: Sequence[int] = (0,),\n    today: Optional[date] = None,\n) -> List[tuple]:'''" + ''',
''' + "'''    expiry_types: Sequence[ExpiryType] = (),\n    expiry_ranks: Sequence[int] = (0,),\n    expiry_ranks_by_type: Optional[dict] = None,\n    today: Optional[date] = None,\n) -> List[tuple]:'''" + ''')'''
new = '''text = Path(STRIKES).read_text()
needle = ''' + "'''    expiry_types: Sequence[ExpiryType] = (),\n    expiry_ranks: Sequence[int] = (0,),\n    today: Optional[date] = None,\n) -> List[tuple]:'''" + '''
replacement = ''' + "'''    expiry_types: Sequence[ExpiryType] = (),\n    expiry_ranks: Sequence[int] = (0,),\n    expiry_ranks_by_type: Optional[dict] = None,\n    today: Optional[date] = None,\n) -> List[tuple]:'''" + '''
start = text.find("def pick_strikes")
pos = text.find(needle, start)
if pos < 0:
    raise RuntimeError("pick_strikes signature anchor missing")
text = text[:pos] + replacement + text[pos + len(needle):]
Path(STRIKES).write_text(text)'''
if old not in text:
    raise RuntimeError('finalize.py duplicate-signature block not found')
p.write_text(text.replace(old, new, 1))
print('finalizer anchor repaired')
