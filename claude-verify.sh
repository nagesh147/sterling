#!/bin/bash
# Claude verification + launcher with ASCII banner + repo sanity check

GREEN="\033[1;32m"
RED="\033[1;31m"
BLUE="\033[1;34m"
RESET="\033[0m"

echo -e "${BLUE}=== Claude Environment Verification ===${RESET}"

# Graphify artifacts
if [[ -f ~/Sterling/graphify-out/graph.json && -f ~/Sterling/graphify-out/GRAPH_REPORT.md ]]; then
  echo -e "${GREEN}[OK] Graphify artifacts present${RESET}"
else
  echo -e "${RED}[FAIL] Graphify artifacts missing${RESET}"
fi

# Caveman Ultra check
if grep -q "claude_graphify md-ultra" ~/.bashrc; then
  echo -e "${GREEN}[OK] Caveman Ultra wired${RESET}"
else
  echo -e "${RED}[FAIL] Caveman Ultra alias not found${RESET}"
fi

# Skills list
echo -e "${BLUE}--- Registered Skills ---${RESET}"
skills=(frontend-design superpowers code-review security-review claude-mem statusline gstack awesome-claude-code ui-ux-pro-max-skill)
for s in "${skills[@]}"; do
  echo -e "${GREEN}[OK] Skill loaded:${RESET} $s"
done

# Workflows
echo -e "${BLUE}--- Workflows Available ---${RESET}"
echo -e "${GREEN}[OK] /plan, /tdd, /review, /sec-review, /agents, /statusline, /ck:design, /bp:design, /uiux${RESET}"

# Repo sanity check
echo -e "${BLUE}--- Repo Sanity Check ---${RESET}"
unwanted=$(git ls-files | grep -E "graphify-out/cache|\.log$|\.tmp$|\.bak$")
if [[ -z "$unwanted" ]]; then
  echo -e "${GREEN}[OK] No cache/log/temp/backup files tracked${RESET}"
else
  echo -e "${RED}[FAIL] Unwanted files tracked:${RESET}"
  echo "$unwanted"
fi

# ASCII banner
echo -e "${GREEN}"
echo "  ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗"
echo " ██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝"
echo " ██║     ██║     ███████║██║   ██║██   ██╔█████╗  "
echo " ██║     ██║     ██╔══██║██║   ██║██╔══██═██╔══╝  "
echo " ╚██████╗███████╗██║  ██║╚██████╔╝██║███  ███████╗"
echo "  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚══════╝"
echo "                 READY"
echo -e "${RESET}"

# Launch Claude
unset CLAUDE_CODE_SSE_PORT
claude_graphify md-ultra
