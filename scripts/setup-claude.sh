#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[0;33m'
CYN='\033[0;36m'; BLD='\033[1m'; RST='\033[0m'
ok()   { echo -e "  ${GRN}✔${RST}  $1"; }
warn() { echo -e "  ${YLW}⚠${RST}  $1"; }

echo -e "${CYN}${BLD}"
echo "=============================================="
echo "  Sterling - Full Claude Setup"
echo "  code-review-graph + TrueCourse + Skills"
echo "=============================================="
echo -e "${RST}"

# ---------- 1. Submodules ----------
echo -e "\n${BLD}1. Git submodules...${RST}"
[ -f .gitmodules ] && git submodule update --init --recursive || warn "no/failed submodules"
ok "Submodules ready"

# ---------- 2. CLI Tools ----------
echo -e "\n${BLD}2. Preferred CLI tools...${RST}"
install_if_missing() {
  local cmd="$1" pkg="$2"
  if command -v "$cmd" &>/dev/null; then ok "$cmd"
  else
    if command -v apt-get &>/dev/null; then
      sudo apt-get install -y -qq "$pkg" >/dev/null 2>&1 && ok "$pkg" || warn "$pkg failed"
    elif command -v brew &>/dev/null; then
      brew install "$pkg" >/dev/null 2>&1 && ok "$pkg" || warn "$pkg failed"
    else warn "Install $pkg manually"; fi
  fi
}
install_if_missing rg ripgrep
install_if_missing fd fd-find
install_if_missing jq jq
install_if_missing gh gh
command -v yq &>/dev/null && ok "yq" || { command -v snap &>/dev/null && sudo snap install yq >/dev/null 2>&1 && ok "yq" || warn "yq missing"; }
if ! command -v sg &>/dev/null && ! command -v ast-grep &>/dev/null; then
  command -v npm &>/dev/null && npm install -g @ast-grep/cli >/dev/null 2>&1 && ok "ast-grep" || warn "ast-grep missing"
else ok "ast-grep"; fi

# ---------- 3. code-review-graph (Primary) ----------
echo -e "\n${BLD}3. code-review-graph (Primary)...${RST}"
if ! command -v code-review-graph &>/dev/null; then
  command -v pipx &>/dev/null && pipx install code-review-graph || pip install --user code-review-graph
  ok "Installed"
else ok "Already installed"; fi
code-review-graph install --platform claude-code || warn "configure warnings"
code-review-graph build || warn "build issues"
ok "Graph built + hooks ready"

# ---------- 4. TrueCourse (Architecture) ----------
echo -e "\n${BLD}4. TrueCourse (Architecture)...${RST}"
if ! command -v truecourse &>/dev/null; then
  if command -v npm &>/dev/null; then
    npm install -g truecourse >/dev/null 2>&1 && ok "truecourse installed" || warn "truecourse install failed"
  else
    warn "npm not found — install Node.js then: npm i -g truecourse"
  fi
else
  ok "truecourse already installed"
fi

if command -v truecourse &>/dev/null; then
  echo "  Running first architecture analysis..."
  truecourse analyze || warn "truecourse analyze had issues (can re-run later)"
  truecourse hooks install 2>/dev/null || warn "truecourse hooks optional"
  ok "TrueCourse ready"
fi

# ---------- 5. Skills ----------
echo -e "\n${BLD}5. Skills...${RST}"
if [ -f "./install-skills.sh" ]; then
  bash ./install-skills.sh update 2>/dev/null || bash ./install-skills.sh install || warn "skills issues"
  ok "Skills updated"
else
  warn "install-skills.sh missing"
fi

GLOBAL_SKILLS="${HOME}/.claude/skills"
mkdir -p "$GLOBAL_SKILLS"
linked=0
for src in \
  "$PROJECT_ROOT/superpowers/skills" \
  "$PROJECT_ROOT/frontend-design/skills" \
  "$PROJECT_ROOT/ui-ux-pro-max-skill/.claude/skills" \
  "$PROJECT_ROOT/claude-mem/plugin/skills" \
  "$PROJECT_ROOT/claude-mem/openclaw/skills" \
  "$PROJECT_ROOT/skills/skills" \
  "$PROJECT_ROOT/.claude/skills"
do
  [ -d "$src" ] || continue
  for skill in "$src"/*; do
    [ -d "$skill" ] || continue
    name=$(basename "$skill")
    [[ "$name" =~ ^(skills|tests|skill-creator|\.system)$ ]] && continue
    target="$GLOBAL_SKILLS/$name"
    if [ ! -e "$target" ] && [ ! -L "$target" ]; then
      ln -sfn "$skill" "$target"
      ((linked++)) || true
    fi
  done
done
ok "Linked $linked project skills"

# ---------- 6. CLAUDE.md ----------
echo -e "\n${BLD}6. CLAUDE.md...${RST}"
[ -f CLAUDE.md ] && ok "Present" || warn "CLAUDE.md missing!"

# ---------- 7. Global MCP ----------
echo -e "\n${BLD}7. Global MCP...${RST}"
python3 - << 'PY'
import json
from pathlib import Path
paths = [Path.home()/".claude.json", Path.home()/".claude"/"settings.json"]
config, config_path = {}, Path.home()/".claude.json"
for p in paths:
    if p.exists():
        try:
            config = json.loads(p.read_text()); config_path = p; break
        except: pass
if "mcpServers" not in config: config["mcpServers"] = {}
if "code-review-graph" not in config["mcpServers"]:
    config["mcpServers"]["code-review-graph"] = {
        "command": "code-review-graph", "args": ["serve"], "type": "stdio"
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))
    print("  ✔  code-review-graph added to global MCP")
else:
    print("  ✔  Global MCP already configured")
PY

# ---------- 8. Skill auto-update hook ----------
echo -e "\n${BLD}8. Auto-update hooks...${RST}"
python3 - << 'PY'
import json
from pathlib import Path
path = Path.home() / ".claude" / "settings.json"
config = {}
if path.exists():
    try: config = json.loads(path.read_text())
    except: pass
if "hooks" not in config: config["hooks"] = {}
if "SessionStart" not in config["hooks"]: config["hooks"]["SessionStart"] = []
exists = any("install-skills.sh" in str(h) for h in config["hooks"]["SessionStart"])
if not exists:
    config["hooks"]["SessionStart"].append({
        "matcher": "",
        "hooks": [{"type": "command", "command": "bash -c '[ -f \"$HOME/Sterling/install-skills.sh\" ] && bash \"$HOME/Sterling/install-skills.sh\" update >/dev/null 2>&1 || true'"}]
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2))
    print("  ✔  Skill auto-update hook added")
else:
    print("  ✔  Skill auto-update already present")
PY

# ---------- 9. .gitignore ----------
echo -e "\n${BLD}9. .gitignore...${RST}"
for entry in ".code-review-graph/" ".truecourse/"; do
  if ! grep -qF "$entry" .gitignore 2>/dev/null; then
    echo -e "\n# AI tooling\n$entry" >> .gitignore
    ok "Added $entry"
  fi
done
ok ".gitignore ready"

# ---------- Done ----------
echo -e "\n${GRN}${BLD}"
echo "=============================================="
echo "  ✅  Full setup complete!"
echo "=============================================="
echo -e "${RST}"
echo "Installed & configured:"
echo "  • code-review-graph   → Primary (daily coding + token savings)"
echo "  • TrueCourse          → Architecture (circular deps, layers, god modules)"
echo "  • Skills              → 100+ skills + auto-update"
echo "  • CLI tools           → rg, fd, sg, jq, yq, gh"
echo "  • CLAUDE.md           → Optimized rules"
echo
echo "Next steps:"
echo "  1. Restart Claude Desktop App completely"
echo "  2. Open Sterling"
echo "  3. Start a NEW session"
echo
echo "Useful commands:"
echo "  truecourse analyze          # Architecture health"
echo "  truecourse dashboard        # Interactive UI"
echo "  truecourse list             # Violations"
echo "  code-review-graph update    # Refresh graph"
echo
