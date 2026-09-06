// Kite-specific Telegram alert targets — frontend types.
// Mirrors the backend contract in app/api/v1/endpoints/kite_telegram.py.
// Dedicated Kite Telegram configuration:
// the Kite app manages its OWN multiple bots/chats, scoped per user.

/** A managed Telegram alert target as returned by the API (token never echoed). */
export interface KiteTelegramTarget {
  id: string;
  label: string;
  chat_id: string;
  /** Last 6 chars of the bot token (never the full token). */
  bot_token_hint: string;
  /** Whether a bot token is stored for this target. */
  bot_token_set: boolean;
  enabled: boolean;
  /** True once a test message was delivered successfully. */
  reachable: boolean;
}

/** GET /api/v1/kite/telegram response. */
export interface KiteTelegramTargetList {
  targets: KiteTelegramTarget[];
}

/** Body for POST (create) — all fields required. */
export interface KiteTelegramTargetIn {
  label: string;
  bot_token: string;
  chat_id: string;
  enabled: boolean;
}

/** Body for PUT (patch) — all fields optional. */
export interface KiteTelegramTargetPatch {
  label?: string;
  bot_token?: string;
  chat_id?: string;
  enabled?: boolean;
}
