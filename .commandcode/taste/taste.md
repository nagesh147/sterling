# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# architecture
- Keep all functions under engines/ strictly pure: no DB calls, no time.time(), no I/O, no live exchange calls inside engines. Confidence: 0.85
- Schemas must be additive-only: new fields must be Optional with defaults, no breaking changes to existing Pydantic schemas. Confidence: 0.75

# trading-platform
- Use Delta Exchange as the default data source, not Deribit. Confidence: 0.65

# strategy
- Optimize strategies by priority: EXPECTANCY > PF > MAXDD > CONSISTENCY > TRADE COUNT > WIN RATE. Confidence: 0.70

