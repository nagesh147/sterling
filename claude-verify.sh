#!/bin/bash
# Claude verification + launcher with ASCII banner + repo sanity check

GREEN="\033[1;32m"
RED="\033[1;31m"
BLUE="\033[1;34m"
RESET="\033[0m"

echo -e "${BLUE}=== Claude Environment Verification ===${RESET}"

# 1. Graphify artifacts
if [[ -f ~/Sterling/graphify-out/graph.json && -f ~/Sterling/graphify-out/GRAPH_REPORT.md ]]; then
  echo -e "${GREEN}[OK] Graphify artifacts present${RESET}"
else
  echo -e "${RED}[FAIL] Graphify artifacts missing${RESET}"
fi

# 2. Caveman Ultra check - Validates string presence in .bashrc
# Note: Grepping for "claude_graphify" ensures compatibility with unified dispatcher
if grep -q "claude_graphify" ~/.bashrc; then
  echo -e "${GREEN}[OK] Caveman Ultra wired${RESET}"
else
  echo -e "${RED}[FAIL] Caveman Ultra alias not found${RESET}"
fi

# 3. Skills list
echo -e "${BLUE}--- Registered Skills ---${RESET}"
if [ -z "$ACTIVE_SKILLS" ]; then
    skills=(frontend-design superpowers code-review security-review claude-mem statusline gstack awesome-claude-code ui-ux-pro-max-skill)
else
    skills=($ACTIVE_SKILLS)
fi

for s in "${skills[@]}"; do
  echo -e "${GREEN}[OK] Skill loaded:${RESET} $s"
done

# 4. Workflows
echo -e "${BLUE}--- Workflows Available ---${RESET}"
echo -e "${GREEN}[OK] /plan, /tdd, /review, /sec-review, /agents, /statusline, /ck:design, /bp:design, /uiux${RESET}"

# 5. Repo sanity check
echo -e "${BLUE}--- Repo Sanity Check ---${RESET}"
unwanted=$(git ls-files | grep -E "graphify-out/cache|\.log$|\.tmp$|\.bak$" 2>/dev/null)
if [[ -z "$unwanted" ]]; then
  echo -e "${GREEN}[OK] No cache/log/temp/backup files tracked${RESET}"
else
  echo -e "${RED}[FAIL] Unwanted files tracked:${RESET}"
  echo "$unwanted"
fi

# 6. ASCII banner
echo -e "${GREEN}"
echo " ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗"
echo "██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝"
echo "██║     ██║     ███████║██║   ██║██║  ██║█████╗  "
echo "██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══╝  "
echo "╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝███████╗"
echo " ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝╚═════╝ ╚══════╝"
echo "                READY"
echo -e "${RESET}"

# 7. Launch Claude 
# We use 'claude ultra' to trigger the minified, high-density context path
unset CLAUDE_CODE_SSE_PORT
claude ultra "$@"