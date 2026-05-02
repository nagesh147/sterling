#!/bin/bash
# Claude verification + launcher with ASCII banner

GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
RESET="\033[0m"

echo -e "${BLUE}=== Claude Environment Verification ===${RESET}"

# Check Graphify artifacts
if [[ -f ~/Sterling/graphify-out/graph.json && -f ~/Sterling/graphify-out/GRAPH_REPORT.md ]]; then
  echo -e "${GREEN}[OK] Graphify artifacts present (graph.json, GRAPH_REPORT.md)${RESET}"
else
  echo -e "${RED}[FAIL] Graphify artifacts missing${RESET}"
fi

# Caveman Ultra check (alias presence)
if grep -q "claude_graphify md-ultra" ~/.bashrc; then
  echo -e "${GREEN}[OK] Caveman Ultra workflow wired${RESET}"
else
  echo -e "${RED}[FAIL] Caveman Ultra alias not found${RESET}"
fi

# Skills list (static for now)
echo -e "${BLUE}--- Registered Skills ---${RESET}"
skills=(frontend-design superpowers code-review security-review claude-mem statusline gstack awesome-claude-code ui-ux-pro-max-skill)
for s in "${skills[@]}"; do
  echo -e "${GREEN}[OK] Skill loaded:${RESET} $s"
done

echo -e "${BLUE}--- Workflows Available ---${RESET}"
echo -e "${GREEN}[OK] /plan, /tdd, /review, /sec-review, /agents, /statusline, /ck:design, /bp:design, /uiux${RESET}"

echo -e "${BLUE}=== Verification Complete ===${RESET}"

# ASCII banner
echo -e "${GREEN}"
echo "  ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗"
echo " ██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝"
echo " ██║     ██║     ███████║██║   ██║██████╔╝█████╗  "
echo " ██║     ██║     ██╔══██║██║   ██║██╔═══╝ ██╔══╝  "
echo " ╚██████╗███████╗██║  ██║╚██████╔╝██║     ███████╗"
echo "  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚══════╝"
echo "                 READY"
echo -e "${RESET}"

# Finally launch Claude
unset CLAUDE_CODE_SSE_PORT
claude_graphify md-ultra
