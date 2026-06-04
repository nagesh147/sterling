from app.services import paper_store
positions = paper_store.list_positions()
for p in positions:
    if p.status.value in ("open", "partially_closed"):
        print(f"ID: {p.id}")
        print(f"Underlying: {p.underlying}")
        print(f"Direction: {p.sized_trade.structure.direction.value}")
        print(f"Entry: {p.entry_spot_price}")
        print(f"Structure Type: {p.sized_trade.structure.structure_type}")
        print(f"Legs: {len(p.sized_trade.structure.legs)}")
        if p.sized_trade.structure.legs:
            print(f"Leg Delta: {p.sized_trade.structure.legs[0].delta}")
        print("---")
