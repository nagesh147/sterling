# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# architecture
- Keep all functions under engines/ strictly pure: no DB calls, no time.time(), no I/O, no live exchange calls inside engines. Confidence: 0.85
- Schemas must be additive-only: new fields must be Optional with defaults, no breaking changes to existing Pydantic schemas. Confidence: 0.75

# trading-platform
- Use Delta Exchange as the default data source, not Deribit. Confidence: 0.65

# strategy
- Optimize strategies by priority: EXPECTANCY > PF > MAXDD > CONSISTENCY > TRADE COUNT > WIN RATE. Confidence: 0.70

# ui-ux
- Use side panels/drawers for advanced settings rather than inline configuration sections. Keep default view simple with signals only; hide advanced config behind a toggle. Confidence: 0.75
- Add expand/collapse to all sidebar sections for better information density management. Confidence: 0.70

# trading-platform
- When auto/algo trading mode is enabled, automatically execute signals on both paper and live trading (when live is enabled). Confidence: 0.65

# ui-design
- Use side panels for advanced settings and configuration, not inline expandable sections in the main layout. Confidence: 0.70
- Make all sidebar sections (Navigation, Filter, Key Levels, Summary, By Strategy) individually expandable/collapsible. Confidence: 0.75
- Signal-centric UI: the primary view should show signals with entry, exit, and execution buttons; hide advanced configuration by default. Confidence: 0.70

# trading-execution
- Support three distinct trading modes: Paper, Shadow, and Live with clear visual differentiation between them. Confidence: 0.75

# ui-ux
- Avoid duplicate API key entry flows — credentials should only be entered in Exchange Settings, not re-entered in toggle components or modals. Confidence: 0.70
- Green color indicates ON/active/positive states, red indicates OFF/stop/danger in trading UI — consistent with Delta Exchange and Telegram conventions. Confidence: 0.70
- Disable save/submit buttons in settings forms when field values are unchanged from their persisted state, matching the Delta Exchange credentials save pattern. Confidence: 0.60

# ui-formatting
- Format backend reason strings for user-facing display: fix casing (title/sentence case where appropriate), correct grammar, and use readable labels — never show raw-backend underscore_delimited or ALL_CAPS strings directly to users. Confidence: 0.65

# engineering-philosophy
- No MVPs, no band-aids, no shortcuts: build production-grade infrastructure the right way the first time, regardless of time cost. Confidence: 0.80

# ui-layout
See [ui-layout/taste.md](ui-layout/taste.md)
