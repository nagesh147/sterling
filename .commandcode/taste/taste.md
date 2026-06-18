# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# architecture
- Keep all functions under engines/ strictly pure: no DB calls, no time.time(), no I/O, no live exchange calls inside engines. Confidence: 0.85
- Schemas must be additive-only: new fields must be Optional with defaults, no breaking changes to existing Pydantic schemas. Confidence: 0.75
- Kite engine is exclusive and self-contained: do not import or reuse strategy/signal/options/derivative logic from other engines. The Kite module stands alone with its own primitives. Confidence: 0.80

# debugging
- When user reports a signal visible on a chart but missing in the app, clarify which signal table/engine they are referring to (directional, Kite triple super trend, scalping, or derivatives) before investigating the pipeline. Confidence: 0.65

# infrastructure
- Handle Zerodha Kite session refresh automatically: auto-capture refresh_token, auto-refresh access tokens before expiry (~6 AM IST daily), and prevent session lapses without manual user intervention. Confidence: 0.70

# trading-platform
- Use Delta Exchange as the default data source, not Deribit. Confidence: 0.65
- Zerodha Kite must have its own exclusive live/paper toggle, independent of the crypto-specific live/paper toggle. The crypto toggle should not affect Kite trading and vice versa. Confidence: 0.70
- Top-level navigation uses two tabs: Kite and Crypto. All crypto-related tabs (Sterling, Grok, Sterling V2, positions, backtest, paper research, toggles, settings) live under the Crypto tab. Both Kite and Crypto tabs remain always visible — do not hide Crypto when scalp_mode is off; instead provide a user-toggleable show/hide setting for the Crypto tab. Confidence: 0.75

# strategy
- Optimize strategies by priority: EXPECTANCY > PF > MAXDD > CONSISTENCY > TRADE COUNT > WIN RATE. Confidence: 0.70

# ui-ux
- Use side panels/drawers for advanced settings rather than inline configuration sections. Keep default view simple with signals only; hide advanced config behind a toggle. Confidence: 0.75
- Add expand/collapse to all sidebar sections for better information density management. Confidence: 0.70
- Settings toggles and controls should include a concise info/description line explaining what the current setting does or what state is active — not just the toggle label alone. Confidence: 0.65

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
- Display expiry dates (YYYY-MM-DD) as "{day}{ordinal} {MON} {year}" format — e.g., "23rd JUN 2026" with ordinal suffix (st/nd/rd/th), abbreviated uppercase month, and four-digit year. Confidence: 0.70
- Format backend reason strings for user-facing display: fix casing (title/sentence case where appropriate), correct grammar, and use readable labels — never show raw-backend underscore_delimited or ALL_CAPS strings directly to users. Confidence: 0.65
- Use descriptive human-readable labels with parenthetical clarifications in dropdown/select options instead of raw technical identifiers (e.g., "Trend following (futures)" not "directional_futures", "Buy only" not "long_only"). Confidence: 0.70
- Parse and display option tradingsymbols in human-readable format: extract underlying name, strike price, option type (CE/PE), and expiry date — display as "{underlying} {strike} {type} · {formatted expiry}" using two-digit year (e.g., "SENSEX 75500 PE · 18 June 26" from "SENSEX2661875500PE"). Confidence: 0.75

# naming
- Use "Sterling's Gate" for the routing gate component and "Claude's Native" for the native engine component in UI labels and user-facing text. Confidence: 0.80
- When a tab or component is renamed, propagate the rename throughout the entire codebase — update all references, imports, labels, and related identifiers consistently. Confidence: 0.70

# ui-ux
- Strategy profiles must be user-selectable in the UI, not hardcoded or fixed — users should be able to change/choose which profile is active for a signal or strategy. Confidence: 0.70

# ui-components
- Use chip toggles (pill-shaped toggle buttons) instead of checkboxes for boolean/flag options and instead of dropdowns for mode selection — apply this pattern broadly across all option types (alpha sources, engine modes, risk posture, validation options). Confidence: 0.75
- Avoid duplicate APPLY/RESET buttons in child components when the parent already provides them — child settings should participate in the parent's draft/apply flow instead of having their own save controls. Confidence: 0.70
- For the strategy column in data tables: use plain text labels with no colors, no background, and no chip/pill styling. Confidence: 0.70

# ui-ux
- Settings panels should use save-on-apply pattern: show current defaults highlighted, indicate when values differ from defaults, and only persist changes on explicit Apply click — not auto-save. Confidence: 0.70

# engineering-philosophy
- No MVPs, no band-aids, no shortcuts: build production-grade infrastructure the right way the first time, regardless of time cost. Confidence: 0.80

# ui-typography
- Normalize UI font weights: use fontWeight 700 for primary headings/emphasis (never 800), fontWeight 600 for secondary labels/badges/buttons (never 700 or 800 for non-headings), and fontWeight 400 for body text. Confidence: 0.65
- Set minimum font size of 9px for all user-facing UI text (badges, hints, secondary labels); use 10px for table cells and form labels; never use 7-8px for readable text. Confidence: 0.65
- Use var(--t-muted) (not var(--t-dim)) for secondary/descriptive text across all UI components — descriptions, hints, labels, and non-primary metadata. Confidence: 0.65
- Relax letter spacing across UI: use 0.04em-0.06em for labels and headers (not 0.08em-0.12em) to reduce visual tension. Confidence: 0.60

# ui-layout
See [ui-layout/taste.md](ui-layout/taste.md)
- Right sidebar must be user-resizable/extendible, not fixed-width. Confidence: 0.70
- Bottom taskbar should be the single consolidated location for sidebar control icons: hide/show toggles, reset widths, and lock. Remove sidebar controls from the individual sidebars. Confidence: 0.70

# ui-workflow
- Background scanning engines should run automatically without requiring the user to manually click a "scan" button. Scan status and terminal output should always be visible so the user knows what's running. Confidence: 0.70
- When displaying scan status, show what specifically is being scanned (e.g., "Scanning BTC options…", "Scanning ETH futures…") instead of a generic "scanning…" indicator — the label should identify the active scan target. Confidence: 0.70
- Cache and reuse historical scan data when markets are closed — avoid re-scanning unchanged data outside market hours. Only actively poll/refresh during live market hours when data can actually change. Confidence: 0.60

# ui-symbols
- Core symbols (BTC, ETH, SOL) in Global Strategy Config > SYMBOLS must stay always present but be individually toggleable (enable/disable) — never deletable and never permanently locked. Use a checkbox or similar on/off control, not a remove (×) button. Confidence: 0.75

# ui-tables
- Avoid browser-native `title` attribute hover tooltips on table headers — show descriptions inline as a second descriptive line below the header label using `fontSize: 8`, `fontWeight: 400`, muted color, no letter-spacing, no text-transform. Confidence: 0.70
- Show Greeks (IV, delta Δ, gamma Γ, theta Θ, vega V) and Lot size on row expand in both MarketWatch and TripleSupertrend tables. Format as: IV x.x%, Δ delta x.xxx, Γ gamma x.xxxxx, Θ theta/day x.x, V vega x.x, Lot N. Confidence: 0.80

# scan-configuration
- Provide granular scan selection controls: users should be able to independently toggle stocks/indices, spot/derivatives, and ITM/ATM/OTM strike types for each scan strategy. Display scan cost estimates based on the user's current selection to help them understand the data and cost impact. Confidence: 0.75
- "All F&O" toggle should only enable stocks from the curated app registry, not the full exchange F&O universe (~190 stocks). Users must be able to add/remove individual stocks beyond the curated tiers. Confidence: 0.65
- Support historical scan with flexible date range presets: today, yesterday, last 5 days, last week, 15 days, month, and custom range. Historical scans help users verify scan logic and review past signals. Today should remain the default/primary view. Confidence: 0.75
- Allow users to select option expiries in scan settings: provide separate toggle controls for weekly and monthly expiries, following the same UX pattern as stocks/indices and strikes/moneyness selection. Confidence: 0.70

# backend-lifespan
- Background WebSocket managers and stream services must NOT auto-start at module import time (no `manager.start()` at module level). All crypto-related background processes must be explicitly started from the FastAPI lifespan, gated behind the `scalp_mode` kill switch so they stay completely stopped when crypto engines are off. Confidence: 0.75

# git-workflow
- When user says "push all code; sync branches;updated;", run: git status, git add -A, git commit with structured message ("chore: sync {module} — {details}") including Co-authored-by: CommandCodeBot trailer, git push origin {current-branch}, git fetch origin main && git merge origin/main, then report push hash and main status. Confidence: 0.80
