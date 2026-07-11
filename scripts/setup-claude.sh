#!/usr/bin/env bash
set -euo pipefail

# ============================================
# Sterling - Full Claude Code Setup
# One command to set up everything for new clones
# ============================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
CYN='\033[0;36m'
BLD='\033[1m'
RST='\033[0m'

echo -e "${CYN}${BLD}"
echo "========================================"
echo "  Sterling - Full Claude Code Setup"
echo "========================================"
echo -e "${RST}"

# ---------- Helper ----------
ok()   { echo -e "  ${GRN}✔${RST}  $1"; }
warn() { echo -e "  ${YLW}⚠${RST}  $1"; }
fail() { echo -e "  ${RED}✘${RST}  $1"; }

# ---------- 1. Init Git Submodules ----------
echo -e "\n${BLD}1. Initializing git submodules...${RST}"
if [ -f .gitmodules ]; then
  git submodule update --init --recursive || warn "Some submodules failed (continuing)"
  ok "Submodules initialized"
else
  warn "No .gitmodules found"
fi

# ---------- 2. Install Preferred CLI Tools ----------
echo -e "\n${BLD}2. Installing preferred CLI tools...${RST}"

install_if_missing() {
  local cmd="$1"
  local pkg="$2"
  if command -v "$cmd" &>/dev/null; then
    ok "$cmd already installed"
  else
    echo -n "  Installing $pkg ... "
    if command -v apt-get &>/dev/null; then
      sudo apt-get install -y -qq "$pkg" >/dev/null 2>&1 && echo -e "${GRN}done${RST}" || echo -e "${YLW}failed (install manually)${RST}"
    elif command -v brew &>/dev/null; then
      brew install "$pkg" >/dev/null 2>&1 && echo -e "${GRN}done${RST}" || echo -e "${YLW}failed${RST}"
    else
      echo -e "${YLW}skipped (no package manager)${RST}"
    fi
  fi
}

# Core tools from CLAUDE.md
install_if_missing "rg" "ripgrep"
install_if_missing "fd" "fd-find"
install_if_missing "jq" "jq"
install_if_missing "gh" "gh"

# yq (special)
if ! command -v yq &>/dev/null; then
  echo -n "  Installing yq ... "
  if command -v snap &>/dev/null; then
    sudo snap install yq >/dev/null 2>&1 && echo -e "${GRN}done${RST}" || echo -e "${YLW}failed${RST}"
  else
    echo -e "${YLW}install manually: https://github.com/mikefarah/yq${RST}"
  fi
else
  ok "yq already installed"
fi

# ast-grep (sg)
if ! command -v sg &>/dev/null && ! command -v ast-grep &>/dev/null; then
  echo -n "  Installing ast-grep ... "
  if command -v cargo &>/dev/null; then
    cargo install ast-grep --locked >/dev/null 2>&1 && echo -e "${GRN}done${RST}" || echo -e "${YLW}failed${RST}"
  elif command -v npm &>/dev/null; then
    npm install -g @ast-grep/cli >/dev/null 2>&1 && echo -e "${GRN}done${RST}" || echo -e "${YLW}failed${RST}"
  else
    echo -e "${YLW}install manually: https://ast-grep.github.io${RST}"
  fi
else
  ok "ast-grep already installed"
fi

# ---------- 3. Install code-review-graph ----------
echo -e "\n${BLD}3. Installing code-review-graph...${RST}"
if ! command -v code-review-graph &>/dev/null; then
  if command -v pipx &>/dev/null; then
    pipx install code-review-graph
  else
    pip install --user code-review-graph
  fi
  ok "code-review-graph installed"
else
  ok "code-review-graph already installed"
fi

# Configure + Build
echo "  Configuring for Claude Code..."
code-review-graph install --platform claude-code || warn "configure had warnings"

echo "  Building knowledge graph (this can take a few minutes)..."
code-review-graph build || warn "graph build had issues (you can re-run later)"
ok "Graph ready"

# ---------- 4. Install / Update Skills ----------
echo -e "\n${BLD}4. Installing skills...${RST}"
if [ -f "./install-skills.sh" ]; then
  bash ./install-skills.sh install || warn "install-skills.sh had issues"
  ok "Skills installed via install-skills.sh"
else
  warn "install-skills.sh not found — skipping skill repo install"
fi

# Also link any skills that live as submodules inside the project
GLOBAL_SKILLS="${HOME}/.claude/skills"
mkdir -p "$GLOBAL_SKILLS"

SKILL_SOURCES=(
  "$PROJECT_ROOT/superpowers/skills"
  "$PROJECT_ROOT/frontend-design/skills"
  "$PROJECT_ROOT/ui-ux-pro-max-skill/.claude/skills"
  "$PROJECT_ROOT/claude-mem/plugin/skills"
  "$PROJECT_ROOT/claude-mem/openclaw/skills"
  "$PROJECT_ROOT/skills/skills"
  "$PROJECT_ROOT/.claude/skills"
)

linked=0
for src in "${SKILL_SOURCES[@]}"; do
  if [ -d "$src" ]; then
    for skill in "$src"/*; do
      [ -d "$skill" ] || continue
      name=$(basename "$skill")
      if [[ "$name" == "skills" || "$name" == "tests" || "$name" == "skill-creator" || "$name" == ".system" ]]; then
        continue
      fi
      target="$GLOBAL_SKILLS/$name"
      if [ ! -e "$target" ] && [ ! -L "$target" ]; then
        ln -sfn "$skill" "$target"
        ((linked++)) || true
      fi
    done
  fi
done
ok "Linked $linked additional skills into $GLOBAL_SKILLS"

# ---------- 5. Ensure optimized CLAUDE.md ----------
echo -e "\n${BLD}5. Checking CLAUDE.md...${RST}"
if [ -f "CLAUDE.md" ]; then
  ok "CLAUDE.md is present"
else
  fail "CLAUDE.md is missing! Please commit the optimized version."
fi

# ---------- 6. Global MCP Registration ----------
echo -e "\n${BLD}6. Registering global MCP...${RST}"
python3 - << 'PY'
import json
from pathlib import Path

config_paths = [
    Path.home() / ".claude.json",
    Path.home() / ".claude" / "settings.json",
]

config = {}
config_path = Path.home() / ".claude.json"

for p in config_paths:
    if p.exists():
        try:
            config = json.loads(p.read_text())
            config_path = p
            break
        except Exception:
            pass

if "mcpServers" not in config:
    config["mcpServers"] = {}

if "code-review-graph" not in config["mcpServers"]:
    config["mcpServers"]["code-review-graph"] = {
        "command": "code-review-graph",
        "args": ["serve"],
        "type": "stdio"
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))
    print("  ✔  Added code-review-graph to global MCP config")
else:
    print("  ✔  Global MCP already has code-review-graph")
PY

# ---------- 7. Ensure .gitignore has the right entries ----------
echo -e "\n${BLD}7. Checking .gitignore...${RST}"
if ! grep -q ".code-review-graph" .gitignore 2>/dev/null; then
  echo -e "\n# code-review-graph\n.code-review-graph/" >> .gitignore
  ok "Added .code-review-graph/ to .gitignore"
else
  ok ".gitignore already correct"
fi

# ---------- Done ----------
echo -e "\n${GRN}${BLD}"
echo "========================================"
echo "  ✅  Full setup complete!"
echo "========================================"
echo -e "${RST}"
echo "What was set up:"
echo "  • Git submodules initialized"
echo "  • Preferred CLI tools (rg, fd, jq, yq, gh, ast-grep)"
echo "  • code-review-graph installed + graph built"
echo "  • Skills installed & linked globally"
echo "  • CLAUDE.md ready"
echo "  • Global MCP registered"
echo
echo -e "${BLD}Next steps:${RST}"
echo "  1. Fully restart Claude Desktop App"
echo "  2. Open the Sterling project"
echo "  3. Start a NEW session"
echo
echo "To verify later, run:"
echo "  bash claude-verify.sh   # if you have it"
echo "  or paste the master verification prompt into Claude"
echo
