from pathlib import Path

p = Path('.github/expiry-series/apply.py')
text = p.read_text()
old = '''once(STRIKES,
''' + "'''    moneynesses: Sequence[Moneyness], min_dte: int = 0,\n    expiry_types: Sequence[ExpiryType] = (),\n    today: Optional[date] = None,\n) -> List[tuple]:'''" + ''',
''' + "'''    moneynesses: Sequence[Moneyness], min_dte: int = 0,\n    expiry_types: Sequence[ExpiryType] = (),\n    expiry_ranks: Sequence[int] = (0,),\n    today: Optional[date] =