# Kite settings redesign + Kite-specific Telegram

**Date:** 2026-06-19 · **Branch:** KiteEngine · **Status:** Approved — implementing in one pass

## Goal
Three things, all Kite-specific and Kite-faithful (light theme, orange `#f06428`):
1. Redesign the Sterling Kite Engine settings drawer for readability. Ship **both** a
   tabbed layout and a collapsible-cards layout; the user picks which via a control
   in the **Connect** tab. Persisted preference.
2. Give the Kite app its **own Telegram** (separate bot(s)/chat from the crypto
   global one), with **multiple bots you can add/manage**, **test + connection
   status**, and **first-run step-by-step instructions**.
3. The Kite Telegram + the layout chooser live in a new **Kite Settings** area on
   the Connect tab. The global crypto Telegram (Sterling Dashboard) is untouched.

## Part 1 — SuperTrend settings drawer (both layouts)

File: `frontend/src/components/kite/SterlingKiteEnginePane.tsx` (settings drawer at
lines ~1272–1439). Keep ALL existing state/handlers and the save path
(`useSetEngineConfig` → `POST /api/v1/kite/engine/config`). Only reorganize the JSX.

- Preference: `useKiteSettings.engineSettingsLayout: 'tabs' | 'cards'` (added; default
  `'tabs'`, persisted). Drawer renders the chosen layout.
- **Live summary header** (both layouts): one line built from current config, e.g.
  `Derivatives · 11 strikes · 2 idx + 12 stocks · ~2 min/scan` (reuse the existing
  cost computation near line ~1360).
- Three groups, same controls (reuse `Segmented`/`Chip`/`Switch`):
  - **Scan**: Scan source, Strikes (ITM5…OTM5), Expiries (indices W/M, stocks W/M).
  - **Universe**: index chips + stock tiers (VERY HIGH/HIGH/GOOD/OPTIONAL/CUSTOM + add).
  - **Execution**: Exit trailing, Lock profits early, Auto-execute, Kite LIVE.
- `'tabs'`: tab bar [Scan | Universe | Execution] + active-tab content; remember the
  active tab in localStorage.
- `'cards'`: three labeled collapsible cards; **Universe collapsed by default** to a
  summary line (`2 idx + 12 stocks +`); each card independently expand/collapse,
  state in localStorage.
- Tightened spacing: consistent row = left label (fixed width) + control; even
  vertical rhythm; section labels uppercase dim like today.

## Part 2 — Backend: Kite-specific Telegram targets

New, Kite-scoped (per `get_current_user`, like the rest of `kite.py`), persisted.

**Model** — a list of alert targets per user. Each:
`{ id: str, label: str, chat_id: str, bot_token: str (write-only), enabled: bool }`.
Bot tokens stored **encrypted at rest** reusing the Kite-account credential
encryption util (find what `exchanges/kite/accounts.py` uses; do NOT invent new
crypto). Responses never include the raw token — only `bot_token_hint` (last 6).

**Persistence:** via the existing app DB config store (`db.set_config`/`get_config`
JSON) under a per-user key, e.g. `kite_tg_targets:{user_id}`. Reachable flag persisted
per target after a successful test.

**Endpoints** (new router `app/api/v1/endpoints/kite_telegram.py`, registered in the
v1 api router):
- `GET    /api/v1/kite/telegram` → `{ targets: TargetOut[] }`
- `POST   /api/v1/kite/telegram` body `TargetIn` → `TargetOut` (creates, returns id)
- `PUT    /api/v1/kite/telegram/{id}` body `TargetPatch` → `TargetOut`
- `DELETE /api/v1/kite/telegram/{id}` → `{ ok: true }`
- `POST   /api/v1/kite/telegram/{id}/test` → sends a test message via that target's
  token+chat, sets `reachable`, returns `TargetOut`

```
TargetIn    { label: str, bot_token: str, chat_id: str, enabled: bool = true }
TargetPatch { label?: str, bot_token?: str, chat_id?: str, enabled?: bool }
TargetOut   { id: str, label: str, chat_id: str, bot_token_hint: str,
              bot_token_set: bool, enabled: bool, reachable: bool }
```

**Sending:** add `async send_via(token, chat_id, html)` (httpx POST to
`https://api.telegram.org/bot{token}/sendMessage`, `parse_mode=HTML`). Test uses it.

**Wire the alert push:** `services/notifications/telegram_kite.py::push_kite_alerts`
currently sends via the shared global `_tg.TELEGRAM_TOKEN/CHAT_ID`. Change it to send
each fresh signal to **all enabled Kite targets** (per-target token+chat via
`send_via`). **Fallback:** if the user has zero enabled Kite targets, keep the legacy
global behaviour so existing alerts don't silently stop. The interactive `/kite`
control bot (inbound commands/callbacks) stays on the shared bot — out of scope here;
this part is OUTBOUND alerts + test + management only.

## Part 3 — Frontend: Connect Kite-Settings area

Files: new `frontend/src/components/kite/KiteTelegramPanel.tsx`, new hook
`frontend/src/hooks/useKiteTelegram.ts`, new types in
`frontend/src/types/kiteTelegram.ts`; edit `frontend/src/components/kite/ConnectPane.tsx`.

- `useKiteTelegram`: TanStack Query list (`GET`) + mutations add/update/delete/test,
  all invalidating the list. Matches the contract above.
- `KiteTelegramPanel`:
  - **Empty / first-run state:** numbered step-by-step guide:
    1. Open Telegram, message **@BotFather**, send `/newbot`, copy the **bot token**.
    2. Message **@userinfobot** (or your group) to get your **chat id**.
    3. Paste both below, name it, **Add**, then **Test**.
    Each of the two example handles is copyable; the steps are concise and Kite-styled.
  - **Targets list:** one row per bot — label, chat id, token hint, a **status dot**
    (green = reachable, grey = untested/unreachable), an **enable** toggle, **Test**,
    **Edit**, **Remove**. Test shows inline success/fail.
  - **Add bot** form (label, bot token, chat id, enabled) — also used for Edit.
- `ConnectPane`: add a **Kite Settings** section (above account management or after
  the status banner) containing:
  - **Engine settings layout** chooser: a segmented `Tabs | Expand-collapse` bound to
    `useKiteSettings.engineSettingsLayout` (label: "SuperTrend settings layout").
  - The `KiteTelegramPanel`.

## Files
**New:** `backend/app/api/v1/endpoints/kite_telegram.py`;
`frontend/src/components/kite/KiteTelegramPanel.tsx`, `frontend/src/hooks/useKiteTelegram.ts`,
`frontend/src/types/kiteTelegram.ts`.
**Edited:** `frontend/src/store/useKiteSettings.ts` (done — layout pref);
`frontend/src/components/kite/SterlingKiteEnginePane.tsx`;
`frontend/src/components/kite/ConnectPane.tsx`;
`backend/app/services/notifications/telegram_kite.py`; v1 api router registration.

## Verification
- `tsc --noEmit` clean; frontend production build OK.
- Backend: `python -c "import app.main"`-style import/smoke + the new router mounts.
- gstack: drawer in `tabs` and `cards` (toggle via Connect), Connect Telegram empty
  (instructions) and filled (a target row) states.

## Non-goals
- Inbound interactive `/kite` control via per-target bots (stays on the shared bot).
- Touching the global crypto Telegram panel/endpoints.
