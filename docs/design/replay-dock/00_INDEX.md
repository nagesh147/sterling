# Replay Dock — End-to-End Redesign Specification

**Branch:** `design/replay-dock-redesign` (cut from `main` @ `7ff055e1e`)
**Status:** specification only — no implementation in this branch.
**Audience:** an AI coding agent implementing the redesign, plus the human reviewing it.

---

## 0. What this document set is

The Market Replay Dock is Sterling's historical-session player: it replays stored
candles through the signal pipeline and shows the signals and simulated trades that
result. It is mounted inside the Kite workspace and is the only surface in the app
that owns a *time cursor* other than live market time.

This document set is a complete, artifact-by-artifact implementation brief to rebuild
that surface: structure, visual design, motion, transitions, interaction, state,
accessibility, and the backend contract it depends on.

It is written to be executed **in order**. Each artifact doc is self-contained enough
to hand to a single implementation pass, but they share the vocabulary defined in
`02_DESIGN_SYSTEM.md` and the state model in `03_IA_STATES_MOTION.md`. Read those two
first, always.

---

## 1. Read this before writing any code

Two things in `01_GROUND_TRUTH.md` change what "redesign" means here, and they are
verified against the source, not assumed:

1. **Parts of the current UI render data the backend never sends.** The friction /
   slippage system, the option-contract chip, and the "raw ₹" price sub-lines are
   rendered by the frontend but are not produced by `backend/app/services/simulation.py`
   and would be stripped by the FastAPI `response_model` even if they were. A visual
   redesign that faithfully re-renders these is a redesign of a lie.
2. **The end-of-session summary modal has no stylesheet at all.** Its two class names
   are referenced in TSX and defined nowhere, so it currently renders as an unstyled
   block inside the workspace column rather than as a modal.

Therefore the plan below is ordered **honesty first**: `23_A14_backend_contract.md`
(Phase 0) lands before the surfaces that depend on it, and any field the backend does
not send is either implemented backend-side or removed from the UI — never left
rendering a zero that reads as a measurement.

---

## 2. Document map

| # | Document | What it settles |
|---|---|---|
| 01 | [`01_GROUND_TRUTH.md`](01_GROUND_TRUTH.md) | Verified current-state inventory: every file, every defect, with `file:line`. |
| 02 | [`02_DESIGN_SYSTEM.md`](02_DESIGN_SYSTEM.md) | Tokens, type scale, spacing, density, icon rules, colour semantics, motion tokens. |
| 03 | [`03_IA_STATES_MOTION.md`](03_IA_STATES_MOTION.md) | New information architecture, dock modes, the state machine, transitions, keyboard map. |
| 10 | [`10_A01_dock_shell.md`](10_A01_dock_shell.md) | `ReplayDock` — the shell, mode host, mount contract, resize, z-index. |
| 11 | [`11_A02_shell_bar.md`](11_A02_shell_bar.md) | Title bar: identity, live state, clock, window controls. |
| 12 | [`12_A03_transport.md`](12_A03_transport.md) | Transport cluster, speed control, scrub semantics. |
| 13 | [`13_A04_timeline.md`](13_A04_timeline.md) | The scrubbable session timeline + event heatmap. The new centrepiece. |
| 14 | [`14_A05_session_and_filters.md`](14_A05_session_and_filters.md) | Date/session picker, strategy and leg filters. |
| 15 | [`15_A06_metrics_strip.md`](15_A06_metrics_strip.md) | KPI strip. |
| 16 | [`16_A07_signals_table.md`](16_A07_signals_table.md) | Signals feed table. |
| 17 | [`17_A08_trades_table.md`](17_A08_trades_table.md) | Executed trades table. |
| 18 | [`18_A09_config_panel.md`](18_A09_config_panel.md) | Configuration pane. |
| 19 | [`19_A10_summary_modal.md`](19_A10_summary_modal.md) | End-of-session summary (currently unstyled — rebuilt). |
| 20 | [`20_A11_toasts.md`](20_A11_toasts.md) | Signal toast / live event announcements. |
| 21 | [`21_A12_footer_surfaces.md`](21_A12_footer_surfaces.md) | Footer chip, replaying badge, footer status chip. |
| 22 | [`22_A13_store_and_stream.md`](22_A13_store_and_stream.md) | Store shape, transport hook, streaming replaces 150 ms polling. |
| 23 | [`23_A14_backend_contract.md`](23_A14_backend_contract.md) | Backend work: friction engine, contract/spot, SSE, available-dates. |
| 30 | [`30_MIGRATION_PLAN.md`](30_MIGRATION_PLAN.md) | Phase order, file moves, deletions, rollback. |
| 31 | [`31_VERIFICATION.md`](31_VERIFICATION.md) | How each phase is proven. Commands, tests, visual checks. |
| 32 | [`32_ACCEPTANCE_CHECKLIST.md`](32_ACCEPTANCE_CHECKLIST.md) | The single checklist that gates "done". |
| 40 | [`40_IMPLEMENTATION_NOTES.md`](40_IMPLEMENTATION_NOTES.md) | **What actually landed**, where it deviated, what the browser caught, and what is still open. Read this before trusting the specs as a description of the code. |

---

## 3. Design direction, in one paragraph

The current dock is a *settings panel that happens to have a play button*. The redesign
makes it a **transport deck**: the session timeline is the primary object, the transport
is always reachable, configuration recedes into a pane you visit before you press play,
and the results tables are the payload rather than the frame. Visually it stays inside
the Kite terminal's existing token system and density — this is not a new visual
language, it is the same language spoken properly: one type ramp instead of eleven
font sizes, SVG icons instead of emoji, `var(--k-*)` everywhere instead of hardcoded
hex, and motion that is CSS-first, short, and fully disabled under
`prefers-reduced-motion`.

---

## 4. Non-negotiable constraints

These come from the surrounding codebase and are violated by the current implementation
in at least one place each. They are repeated in every artifact doc that can break them.

1. **Tokens only.** Every colour is `var(--k-*)` (see `frontend/src/styles/theme.ts`).
   No literal hex in components. The terminal has a real dark theme; a hardcoded
   `#c2c2c2` or `#efefef` is a dark-mode bug waiting to be filed.
2. **Never static-import `framer-motion`** into the replay dock. The app lazy-gates it
   behind Mac Kite mode; a static import defeats the gate for every user. Replay motion
   is CSS transitions and keyframes.
3. **Respect `prefers-reduced-motion: reduce`** — every animation added must have a
   media-query escape, matching `KiteLayout.tsx:106`.
4. **Body-portal anything that overlays**, with `z-index` above the fullscreen portal
   (`12000`). Header- or column-hosted overlays render behind the page.
5. **Density is a feature.** This is a trading terminal. Row heights stay in the
   26–32 px band; do not "modernise" into 48 px rows.
6. **Direction semantics are fixed:** bullish/long = `--k-green`, bearish/short =
   `--k-red-brick`, target = `--k-amber`, neutral = `--k-dim`. Never re-map these.
7. **No fabricated numbers.** If the backend does not send a field, the UI does not
   invent a `0.00` for it. Show nothing, or show the field's absence explicitly.

---

## 5. How to execute

Work phase by phase from `30_MIGRATION_PLAN.md`. After each phase, run the verification
block for that phase in `31_VERIFICATION.md` and paste the real output into the PR.
Do not mark a phase complete on the strength of "it should work".
