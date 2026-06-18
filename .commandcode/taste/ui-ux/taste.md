# ui-ux
- Use side panels/drawers for advanced settings rather than inline configuration sections. Keep default view simple with signals only; hide advanced config behind a toggle. Confidence: 0.75
- Add expand/collapse to all sidebar sections for better information density management. Confidence: 0.70
- When user opens a buy/sell modal for one symbol and then clicks a different symbol, auto-update the modal with the new symbol's info instead of requiring the user to close and reopen. Confidence: 0.70
- Search list should not close when user clicks "add" on an item; only close when user clicks outside the search/searchlist boundary. Confidence: 0.75
- When selecting limit price in order forms, default to the current market price, not zero. Same for SL and SL-M trigger price fields. Confidence: 0.85
- Move/drag icons should only appear on empty header spaces, not overlaying text, search fields, or other interactive elements. Confidence: 0.70
- Instrument/symbol labels in tables (MarketWatch, signal tables) should follow price direction coloring: green when price is up, red when down — not static k.text (#444444). Apply this consistently everywhere, not just in some tables. Confidence: 0.70
