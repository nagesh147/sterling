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
echo "  Universal Claude Setup"
echo "  graph + TrueCourse + dynamic skills"
echo "=============================================="
echo -e "${RST}"

# ----- 1. Submodules -----
echo -e "\n${BLD}1. Git submodules...${RST}"
if [ -f .gitmodules ]; then
  git submodule update --init --recursive || warn "submodule issues"
  ok "Submodules ready"
else
  warn "No .gitmodules"
fi

# ----- 2. CLI tools -----
echo -e "\n${BLD}2. Preferred CLI tools...${RST}"
install_if_missing() {
  local cmd="$1" pkg="$2"
  if command -v "$cmd" &>/dev/null; then ok "$cmd"; return; fi
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y -qq "$pkg" >/dev/null 2>&1 && ok "$pkg installed" || warn "$pkg failed"
  elif command -v brew &>/dev/null; then
    brew install "$pkg" >/dev/null 2>&1 && ok "$pkg installed" || warn "$pkg failed"
  else
    warn "Install $pkg manually"
  fi
}
install_if_missing rg ripgrep
install_if_missing fd fd-find
install_if_missing jq jq
install_if_missing gh gh
if command -v yq &>/dev/null; then ok "yq"
elif command -v snap &>/dev/null; then sudo snap install yq >/dev/null 2>&1 && ok "yq" || warn "yq missing"
else warn "Install yq manually"; fi
if command -v sg &>/dev/null || command -v ast-grep &>/dev/null; then ok "ast-grep"
elif command -v npm &>/dev/null; then npm install -g @ast-grep/cli >/dev/null 2>&1 && ok "ast-grep" || warn "ast-grep missing"
else warn "Install ast-grep manually"; fi

# ----- 3. code-review-graph (primary) -----
echo -e "\n${BLD}3. code-review-graph (primary)...${RST}"
if ! command -v code-review-graph &>/dev/null; then
  if command -v pipx &>/dev/null; then pipx install code-review-graph
  else pip install --user code-review-graph; fi
  ok "Installed"
else ok "Already installed"; fi
code-review-graph install --platform claude-code || warn "configure warnings"
code-review-graph build || warn "build issues"
ok "Graph built"

# ----- 4. TrueCourse (architecture) -----
echo -e "\n${BLD}4. TrueCourse (architecture)...${RST}"
if ! command -v truecourse &>/dev/null; then
  if command -v npm &>/dev/null; then
    npm install -g truecourse >/dev/null 2>&1 && ok "truecourse installed" || warn "truecourse install failed"
  else warn "Need Node/npm: npm i -g truecourse"; fi
else ok "truecourse already installed"; fi
if command -v truecourse &>/dev/null; then
  truecourse analyze || warn "analyze had issues (re-run later)"
  truecourse hooks install 2>/dev/null || true
  ok "TrueCourse ready"
fi

# ----- 5. Skills (install + update) -----
echo -e "\n${BLD}5. Skills (global, used dynamically)...${RST}"
if [ -f "./install-skills.sh" ]; then
  bash ./install-skills.sh update 2>/dev/null || bash ./install-skills.sh install || warn "skills script issues"
  ok "Skills via install-skills.sh"
else
  warn "install-skills.sh missing — skills not auto-cloned"
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
ok "Linked $linked project skills into ~/.claude/skills"
echo "  (Full skill bodies load only when task matches — see CLAUDE.md routing)"

# ----- 6. CLAUDE.md -----
echo -e "\n${BLD}6. CLAUDE.md...${RST}"
if [ -f CLAUDE.md ]; then
  ok "CLAUDE.md present (dynamic skill router + project rules)"
else
  warn "CLAUDE.md MISSING — copy universal template into repo root"
fi

# ----- 7. Global MCP -----
echo -e "\n${BLD}7. Global MCP (code-review-graph)...${RST}"
python3 - << 'PY'
import json
from pathlib import Path
paths = [Path.home()/".claude.json", Path.home()/".claude"/"settings.json"]
config, config_path = {}, Path.home()/".claude.json"
for p in paths:
    if p.exists():
        try:
            config = json.loads(p.read_text()); config_path = p; break
        except Exception:
            pass
if "mcpServers" not in config:
    config["mcpServers"] = {}
if "code-review-graph" not in config["mcpServers"]:
    config["mcpServers"]["code-review-graph"] = {
        "command": "code-review-graph", "args": ["serve"], "type": "stdio"
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))
    print("  ✔  Added code-review-graph to global MCP")
else:
    print("  ✔  Global MCP already configured")
PY

# ----- 8. Skill auto-update on SessionStart -----
echo -e "\n${BLD}8. Auto-update hooks...${RST}"
python3 - << 'PY'
import json
from pathlib import Path
path = Path.home() / ".claude" / "settings.json"
config = {}
if path.exists():
    try:
        config = json.loads(path.read_text())
    except Exception:
        config = {}
if "hooks" not in config:
    config["hooks"] = {}
if "SessionStart" not in config["hooks"]:
    config["hooks"]["SessionStart"] = []
# Prefer project-local install-skills if present; fallback Sterling home path
cmd = (
    'bash -c \''
    'f=""
    '[ -f ./install-skills.sh ] && f=./install-skills.sh; '
    '[ -z "$f" ] && [ -f "$HOME/Sterling/install-skills.sh" ] && f="$HOME/Sterling/install-skills.sh"; '
    '[ -n "$f" ] && bash "$f" update >/dev/null 2>&1 || true\''
)
exists = any("install-skills.sh" in str(h) for h in config["hooks"]["SessionStart"])
if not exists:
    config["hooks"]["SessionStart"].append({
        "matcher": "",
        "hooks": [{"type": "command", "command": cmd}],
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2))
    print("  ✔  Skill auto-update SessionStart hook added")
else:
    print("  ✔  Skill auto-update hook already present")
PY

# ----- 9. .gitignore -----
echo -e "\n${BLD}9. .gitignore...${RST}"
touch .gitignore
for entry in ".code-review-graph/" ".truecourse/"; do
  if ! grep -qF "$entry" .gitignore 2>/dev/null; then
    echo -e "\n# AI tooling\n$entry" >> .gitignore
    ok "Added $entry"
  fi
done
ok ".gitignore ready"

# ----- Done -----
echo -e "\n${GRN}${BLD}"
echo "=============================================="
echo "  ✅  Setup complete"
echo "=============================================="
echo -e "${RST}"
echo "Stack:"
echo "  • code-review-graph  → daily coding, impact, token savings"
echo "  • TrueCourse         → architecture (cycles, layers, god modules)"
echo "  • Skills             → dynamic 1–3 per task (see CLAUDE.md)"
echo "  • CLI                → rg fd sg jq yq gh"
echo
echo "New users:  ./scripts/setup-claude.sh   OR   make setup-claude"
echo "Then: restart Claude Desktop → open project → NEW session"
echo
