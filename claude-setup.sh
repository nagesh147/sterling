#!/bin/bash
# Bootstrap Claude setup for Sterling repo

set -e

GREEN="\033[1;32m"
BLUE="\033[1;34m"
RESET="\033[0m"

echo -e "${BLUE}=== Sterling Claude Setup ===${RESET}"

# 1. Create Sterling workspace
mkdir -p ~/Sterling
cd ~/Sterling

# 2. Clone skill repos (if not already present)
repos=(
  "https://github.com/obra/superpowers.git"
  "https://github.com/anthropics/skills.git"
  "https://github.com/your-org/security-review.git"
  "https://github.com/your-org/ui-ux-pro-max-skill.git"
)

for repo in "${repos[@]}"; do
  name=$(basename "$repo" .git)
  if [[ ! -d "$name" ]]; then
    echo -e "${GREEN}[CLONE] $name${RESET}"
    git clone "$repo"
  else
    echo -e "${GREEN}[SKIP] $name already present${RESET}"
  fi
done

# 3. Update ~/.claude/settings.json with skill paths
echo -e "${BLUE}--- Updating Claude settings ---${RESET}"
mkdir -p ~/.claude
settings=~/.claude/settings.json
tmpfile=$(mktemp)

jq '.skills += {
  "frontend-design":{"path":"'$PWD'/skills/skills/frontend-design","default":true},
  "superpowers":{"path":"'$PWD'/superpowers","default":true},
  "security-review":{"path":"'$PWD'/security-review","default":true},
  "ui-ux-pro-max-skill":{"path":"'$PWD'/ui-ux-pro-max-skill","default":true}
}' "$settings" > "$tmpfile" && mv "$tmpfile" "$settings"

# 4. Build Graphify artifacts
echo -e "${BLUE}--- Building Graphify ---${RESET}"
graphify update ~/Sterling

# 5. Install Caveman Ultra alias
echo -e "${BLUE}--- Wiring Caveman Ultra ---${RESET}"
if ! grep -q "claude_graphify md-ultra" ~/.bashrc; then
  echo "alias claude_graphify='graphify run'" >> ~/.bashrc
  echo "alias claude='~/Sterling/claude-verify.sh'" >> ~/.bashrc
fi

# 6. Verification script already in repo
chmod +x ~/Sterling/claude-verify.sh

echo -e "${GREEN}=== Setup Complete ===${RESET}"
echo -e "${GREEN}Run 'source ~/.bashrc' then 'claude' to verify and launch.${RESET}"
