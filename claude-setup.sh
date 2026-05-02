#!/bin/bash
set -e

echo "=== Claude Setup Script ==="

# Backup existing bashrc
cp ~/.bashrc ~/.bashrc.backup.$(date +%Y%m%d%H%M%S)

# Copy project bashrc into place (if provided)
if [ -f ./bashrc.backup ]; then
  cp ./bashrc.backup ~/.bashrc
  source ~/.bashrc
fi

# Ensure ~/.claude/settings.json exists
mkdir -p ~/.claude
echo '{"skills":{}}' > ~/.claude/settings.json

# Clone/update repos
mkdir -p ~/Sterling && cd ~/Sterling
for repo in \
  "https://github.com/obra/superpowers.git superpowers" \
  "https://github.com/anthropics/skills.git frontend-design" \
  "https://github.com/thedotmack/claude-mem.git claude-mem" \
  "https://github.com/anthropics/claude-code.git code-review" \
  "https://github.com/anthropics/claude-code-security-review.git security-review" \
  "https://github.com/garrytan/gstack.git ~/.claude/skills/gstack" \
  "https://github.com/anthropics/awesome-claude-code.git awesome-claude-code" \
  "https://github.com/anthropics/ui-ux-pro-max-skill.git ui-ux-pro-max-skill"
do
  set -- $repo
  url=$1
  target=$2
  if [ -d "$target/.git" ]; then
    echo "Updating $target..."
    git -C "$target" pull --ff-only
  else
    echo "Cloning $url into $target..."
    git clone "$url" "$target"
  fi
done

# Statusline skill
mkdir -p ~/Sterling/statusline
cat > ~/Sterling/statusline/SKILL.md <<'EOT'
# Statusline Skill
Provides live runtime metrics (tokens, mode, context economics, active skills).
EOT

# Update settings.json
tmp=$(mktemp)
jq '.skills["claude-mem"]={"path":"~/Sterling/claude-mem","commands":["/mem-search","/get_observations"]}
    | .skills["superpowers"]={"path":"~/Sterling/superpowers","commands":["/superpowers"]}
    | .skills["frontend-design"]={"path":"~/Sterling/frontend-design","commands":["/frontend-design"]}
    | .skills["code-review"]={"path":"~/Sterling/code-review","commands":["/review"]}
    | .skills["security-review"]={"path":"~/Sterling/security-review","commands":["/sec-review"]}
    | .skills["gstack"]={"path":"~/.claude/skills/gstack","commands":["/gstack"]}
    | .skills["awesome-claude-code"]={"path":"~/Sterling/awesome-claude-code","commands":["/awesome"]}
    | .skills["ui-ux-pro-max-skill"]={"path":"~/Sterling/ui-ux-pro-max-skill","commands":["/uiux"]}
    | .skills["statusline"]={"path":"~/Sterling/statusline","commands":["/statusline"]}' \
    ~/.claude/settings.json > "$tmp" && mv "$tmp" ~/.claude/settings.json

# Rebuild Graphify artifacts (skip HTML viz)
graphify update ~/Sterling --no-viz || echo "[WARN] Graphify rebuild failed, but JSON/MD may still exist."

# Install claude-verify.sh
cat > ~/Sterling/claude-verify.sh <<'VERIFY'
#!/bin/bash
echo "=== Registered Claude Skills ==="
jq '.skills | to_entries | map({name: .key, commands: .value.commands})' ~/.claude/settings.json

echo "=== Checking Graphify Artifacts ==="
for f in ~/Sterling/graph.json ~/Sterling/GRAPH_REPORT.md; do
  if [ -f "$f" ]; then
    echo "[OK] Found $f"
    stat -c "Last updated: %y" "$f"
  else
    echo "[MISSING] $f not found"
  fi
done

echo "=== Launching Claude with Statusline ==="
claude <<'INNER'
/statusline
INNER
VERIFY
chmod +x ~/Sterling/claude-verify.sh

echo "=== Setup Complete ==="
