#!/usr/bin/env bash
# Create GitHub issues for the Critical/High findings in SECURITY_REVIEW.md
# Prereq: authenticate once with:  "$HOME/.local/gh/bin/gh.exe" auth login
# Then run:  bash create-security-issues.sh
set -euo pipefail

GH="${GH_BIN:-$HOME/.local/gh/bin/gh.exe}"
REPO="nageshmadaram/sterling"

if ! "$GH" auth status >/dev/null 2>&1; then
  echo "ERROR: gh is not authenticated. Run: \"$GH\" auth login" >&2
  exit 1
fi

echo "Creating labels (idempotent)…"
"$GH" label create "security"          --repo "$REPO" --color "5319E7" --description "Security finding"       --force || true
"$GH" label create "severity:critical" --repo "$REPO" --color "B60205" --description "Critical severity"      --force || true
"$GH" label create "severity:high"     --repo "$REPO" --color "D93F0B" --description "High severity"          --force || true

mkissue() {  # $1=title  $2=labels  $3=body
  echo "→ $1"
  "$GH" issue create --repo "$REPO" --title "$1" --label "$2" --body "$3"
}

FOOTER=$'\n\n---\n_Filed from the 2026-08-25 security review. Full report: `SECURITY_REVIEW.md`._'

mkissue "[C1] No authentication on live-order API bound to 0.0.0.0" "security,severity:critical" \
"**Severity: Critical**

\`get_current_user\` (\`backend/app/core/auth.py:28-31\`) trusts the client-supplied \`X-User-Id\` header — no token/session/signature — defaulting to \`\"default\"\`. \`create_app()\` (\`backend/main.py:1750-1852\`) mounts ~30 routers behind only CORS + security headers; \`__main__\` runs \`uvicorn.run(..., host=\"0.0.0.0\", ..., reload=True)\` (\`backend/main.py:1861\`).

**Impact:** anyone who can reach the port can place/cancel live orders, flip the kill-switch, switch the router to LIVE, and CRUD broker credentials — and \`X-User-Id: <victim>\` impersonates any tenant (IDOR).

**Fix:** real authN (JWT/session) at the \`get_current_user\` seam; derive \`user_id\` from verified identity, never a header; bind to \`127.0.0.1\` by default; never \`reload=True\` in production.${FOOTER}"

mkissue "[C2] Auto-trader defaults to LIVE and ignores the paper_trading default" "security,severity:critical" \
"**Severity: Critical**

\`settings.paper_trading=True\` (\`backend/app/core/config.py:8\`) is read only for display, never in a send path. The auto path builds \`DeltaIndiaAdapter(is_paper=False)\` (\`backend/main.py:823-826\`), defaults \`algo_router_mode\` to \`\"live\"\`, and fails open to \`RouterMode.LIVE\` on any parse error (\`backend/main.py:828-834\`, \`:1176-1178\`, \`:1372-1375\`). \`_auto_place_algo_order\` never checks the account's \`is_paper\`.

**Impact:** a user who leaves the documented \`paper_trading=True\` and enables algo mode gets real orders on real funds on the first strong signal — even a paper Delta account does not stop it.

**Fix:** make \`paper_trading=True\` force \`RouterMode.PAPER\`; default the mode to \`\"paper\"\` and fail closed to PAPER on bad input; set the auto adapter's \`is_paper\` from the account/mode; refuse live when \`active.is_paper\`.${FOOTER}"

mkissue "[C3] Broker secrets stored plaintext at rest; encryption keyed by a hardcoded constant" "security,severity:critical" \
"**Severity: Critical**

\`exchange_configs\` declares \`api_key TEXT\`/\`api_secret TEXT\` (not \`*_enc\`) and \`_persist()\` writes them raw (\`backend/app/services/exchange_account_store.py:39-40, 62-64\`) — Delta/Binance/Deribit/OKX. Where encryption is used (Kite), \`security._init()\` falls back to the literal \`\"sterling-dev-insecure-key\"\` when \`STERLING_SECRET_KEY\` is unset, degrades to reversible base64 if \`cryptography\` is missing, and returns un-prefixed legacy values as plaintext (\`backend/app/core/security.py:40-46, 51-65, 79-80\`). \`.gitignore:116-118\` documents that \`sterling_paper.db\` carries these plaintext secrets.

**Impact:** anyone who obtains the SQLite file recovers every live trading credential — as plaintext or under a key printed in public source. (No \`.db\` is currently committed.)

**Fix:** encrypt \`exchange_configs\` secrets; make \`STERLING_SECRET_KEY\` mandatory outside dev; make \`cryptography\` a hard dependency and drop the base64/plaintext fallbacks in production.${FOOTER}"

mkissue "[C4] Idempotency cannot prevent duplicate LIVE orders on timeout/retry" "security,severity:critical" \
"**Severity: Critical**

The dedup key is recorded only after a successful fill (\`backend/app/services/live_safety.py:86-87\`), lives in an in-process dict with a 60s TTL (\`:7\`), is checked non-atomically before \`await place_order\`, and is never sent to the broker (Delta's body has no \`client_order_id\`). On a post-submit timeout the order is live-but-unrecorded, so \`enqueue_retry\` fires and the retry worker re-sends it ≥60s later with no key; concurrent submits race the same window.

**Impact:** the exact scenario the mechanism advertises (timeout → retry) doubles a real position; multi-worker deployments don't share the cache.

**Fix:** generate a stable \`client_order_id\` and send it to the broker so the exchange rejects duplicates; reserve the key before the network call; serialize check-then-act per key; on unknown-outcome exceptions, reconcile via order lookup before re-placing.${FOOTER}"

mkissue "[H1] Greeks budget \"hard gate\" fails OPEN" "security,severity:high" \
"**Severity: High**

\`backend/app/services/execution/order_router.py:285-297\`: \`except Exception: gate_result = None  # fail-open\`. The module docstring claims it \"never silently fails-open.\" If the chain/NAV fetch throws during volatility, a budget-breaching live order proceeds.

**Fix:** reject with \`greeks_budget_unknown\` on gate exception, mirroring \`assert_safe_to_trade\`.${FOOTER}"

mkissue "[H2] Retried orders are re-placed WITHOUT their stop-loss/take-profit bracket" "security,severity:high" \
"**Severity: High**

The retry payload omits SL/TP/trail (\`backend/app/services/execution/order_router.py:347-354\`); the worker re-places a bare market order → an unprotected live position with no exchange-side stop.

**Fix:** carry and re-attach the bracket; refuse to retry an entry that can't include its protection.${FOOTER}"

mkissue "[H3] Unauthenticated SSRF via user-controlled webhook URL" "security,severity:high" \
"**Severity: High**

\`POST /webhooks\` and \`/{id}/test\` have no auth (\`backend/app/api/v1/endpoints/webhooks.py:26,37\`); \`_send\` POSTs to the raw \`wh.url\` (\`backend/app/services/webhook_store.py:208\`); \`WebhookCreate.url\` is a plain \`str\` (\`HttpUrl\` imported but unused). An anonymous caller can hit \`http://169.254.169.254/…\`, localhost, or internal hosts and read reachability from the echoed error.

**Fix:** type as \`HttpUrl\`; https-only allowlist; resolve-and-reject private/link-local/loopback ranges; require auth.${FOOTER}"

mkissue "[H4] SHADOW mode sends REAL orders on the auto path" "security,severity:high" \
"**Severity: High**

\`_submit_shadow\` calls \`_submit_live\` (\`backend/app/services/execution/order_router.py:261\`) — a real order plus a paper twin — while the manual endpoint's comment says shadow \"never touches real funds.\" An operator picking \"shadow\" to observe safely gets live Delta orders.

**Fix:** pick one definition; if shadow must be safe, simulate the fill instead of calling \`_submit_live\`.${FOOTER}"

echo
echo "Done. Open issues:"
"$GH" issue list --repo "$REPO" --label security --limit 20
