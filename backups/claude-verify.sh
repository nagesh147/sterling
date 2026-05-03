#!/bin/bash
# claude-verify.sh — Environment verification + Claude launcher
# Receives pre-built context via $CLAUDE_CTX from the dispatcher.
# Never rebuilds context — consumes what the dispatcher already prepared.

GREEN="\033[1;32m"
RED="\033[1;31m"
BLUE="\033[1;34m"
YELLOW="\033[1;33m"
RESET="\033[0m"

echo -e "${BLUE}=== Claude Environment Verification ===${RESET}"

# 1. Graphify artifacts
if [[ -f ~/Sterling/graphify-out/graph.json && -f ~/Sterling/graphify-out/GRAPH_REPORT.md ]]; then
    echo -e "${GREEN}[OK] Graphify artifacts present${RESET}"
else
    echo -e "${RED}[FAIL] Graphify artifacts missing — run graphify init${RESET}"
fi

# 2. Dispatcher wired correctly
if grep -q "claude_graphify" ~/.bashrc; then
    echo -e "${GREEN}[OK] Sterling dispatcher wired${RESET}"
else
    echo -e "${RED}[FAIL] Sterling dispatcher not found in .bashrc${RESET}"
fi

# 3. Context check — was $CLAUDE_CTX passed from dispatcher?
if [[ -n "${CLAUDE_CTX:-}" ]]; then
    local_lines=$(echo "$CLAUDE_CTX" | wc -l)
    local_words=$(echo "$CLAUDE_CTX" | wc -w)
    echo -e "${GREEN}[OK] Context received — ${local_lines}L / ${local_words} words (~$(( local_words * 13 / 10 )) tokens)${RESET}"
else
    echo -e "${YELLOW}[WARN] No context from dispatcher — will launch without injected skills${RESET}"
fi

# 4. Skills list — uses $ACTIVE_SKILLS exported by dispatcher
echo -e "${BLUE}--- Active Skills ---${RESET}"
if [[ -z "${ACTIVE_SKILLS:-}" ]]; then
    echo -e "${YELLOW}[WARN] ACTIVE_SKILLS not set — dispatcher may not have run${RESET}"
else
    for s in $ACTIVE_SKILLS; do
        echo -e "${GREEN}[OK] $s${RESET}"
    done
fi

# 5. Workflows
echo -e "${BLUE}--- Workflows ---${RESET}"
echo -e "${GREEN}[OK] /plan /tdd /review /sec-review /agents /statusline /ck:design /bp:design /uiux${RESET}"

# 6. Repo sanity check
echo -e "${BLUE}--- Repo Sanity ---${RESET}"
unwanted=$(git ls-files 2>/dev/null | grep -E "graphify-out/cache|\.log$|\.tmp$|\.bak$" || true)
if [[ -z "$unwanted" ]]; then
    echo -e "${GREEN}[OK] No cache/log/temp/backup files tracked${RESET}"
else
    echo -e "${RED}[FAIL] Unwanted files tracked:${RESET}"
    echo "$unwanted"
fi

# 7. Banner
echo -e "${GREEN}"
echo " ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗"
echo "██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝"
echo "██║     ██║     ███████║██║   ██║██║  ██║█████╗  "
echo "██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══╝  "
echo "╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝███████╗"
echo " ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝╚═════╝ ╚══════╝"
echo "                READY"
echo -e "${RESET}"

# 8. Launch Claude using pre-built context from dispatcher
#
# $CLAUDE_CTX  — full context block built by build_context() in .bashrc
# $CLAUDE_CTX_MODE — "system-flag" or "stdin", detected once per session
# claude_real  — the raw claude binary, exported from .bashrc
#
# We never call 'claude ultra' here — that would bypass context injection
# and hit the binary with no skills, no graph, and no memory.

unset CLAUDE_CODE_SSE_PORT

if [[ -n "${CLAUDE_CTX:-}" ]]; then
    case "${CLAUDE_CTX_MODE:-stdin}" in
        system-flag)
            claude_real --system "$CLAUDE_CTX" "$@"
            ;;
        stdin)
            printf '%s\n' "$CLAUDE_CTX" | claude_real "$@"
            ;;
    esac
else
    # No context passed — fall back to raw launch
    claude_real "$@"
fi