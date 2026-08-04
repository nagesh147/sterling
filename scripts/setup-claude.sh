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
# ---------- 4. TrueCourse (Architecture) — interactive for new users ----------
echo -e "
${BLD}4. TrueCourse (architecture)...${RST}"

if ! command -v truecourse &>/dev/null; then
  if command -v npm &>/dev/null; then
    echo
    echo "  truecourse is not installed."
    echo "  Install globally via npm? (free package; needs Node.js)"
    read -r -p "  Install truecourse now? [Y/n] " ans
    ans=${ans:-Y}
    if [[ "$ans" =~ ^[Yy]$ ]]; then
      npm install -g truecourse && ok "truecourse installed" || warn "truecourse install failed"
    else
      warn "Skipped truecourse install"
    fi
  else
    warn "npm missing — skip truecourse (install Node.js to enable)"
  fi
else
  ok "truecourse already installed"
fi

if command -v truecourse &>/dev/null; then
  echo
  echo "  TrueCourse finds architecture issues (circular deps, layer violations,"
  echo "  god/dead modules, coupling, etc.). Choose how to run it NOW:"
  echo
  echo "  1) Deterministic only  [RECOMMENDED for first setup]"
  echo "     - Fast (seconds to a few minutes)"
  echo "     - No LLM / Claude API token cost for rules"
  echo "     - Does not need Claude session quota for LLM rules"
  echo "     - Best default when cloning a repo"
  echo
  echo "  2) Full analysis with LLM rules"
  echo "     - Deeper semantic checks"
  echo "     - Can use a LARGE number of tokens (on big repos: millions)"
  echo "     - Requires working claude CLI and available quota"
  echo "     - Slow; use when you want a deep architecture pass"
  echo
  echo "  3) Skip analysis for now"
  echo "     - Zero time / zero tokens"
  echo "     - You can run truecourse later manually"
  echo
  read -r -p "  Analysis mode [1/2/3] (default: 1): " mode
  mode=${mode:-1}

  case "$mode" in
    2)
      echo "  → Full LLM analysis (high token use)..."
      if truecourse analyze --llm --stash --no-skills; then
        ok "TrueCourse full analysis done"
      else
        warn "Full analysis failed (quota/CLI). Later: truecourse analyze --llm --stash --no-skills"
      fi
      ;;
    3)
      warn "Skipped TrueCourse analyze"
      echo "  Later:"
      echo "    truecourse analyze --no-llm --stash --no-skills"
      echo "    truecourse analyze --llm --stash --no-skills"
      ;;
    *)
      echo "  → Deterministic analysis (no LLM tokens)..."
      if truecourse analyze --no-llm --stash --no-skills; then
        ok "TrueCourse deterministic analysis done"
      else
        warn "Deterministic analyze failed. Later: truecourse analyze --no-llm --stash --no-skills"
      fi
      ;;
  esac

  echo
  echo "  Pre-commit hook? [y/N] (default N)"
  echo "  ┌──────────────────────────────────────────────────────────────────────┐"
  echo "  │ Y — Run TrueCourse on every commit                                 │"
  echo "  │     • Stricter (architecture issues caught earlier)               │"
  echo "  │     • Slower commits on large repos (diff analysis time)          │"
  echo "  │     • Usually NO large LLM token cost (hook uses --diff)          │"
  echo "  │     • Many tokens only if LLM rules are enabled on the hook       │"
  echo "  │                                                                    │"
  echo "  │ N — No hook [RECOMMENDED for most people / large repos]            │"
  echo "  │     • Fast commits                                                 │"
  echo "  │     • Zero hook cost; run truecourse manually when needed          │"
  echo "  └──────────────────────────────────────────────────────────────────────┘"
  read -r -p "  Install TrueCourse pre-commit hook? [y/N] " hook
  hook=${hook:-N}
  if [[ "$hook" =~ ^[Yy]$ ]]; then
    if truecourse hooks install 2>/dev/null; then
      ok "Pre-commit hook installed"
      echo "  Note: hook typically runs diff/deterministic analysis (time cost)."
      echo "        LLM tokens are NOT used on each commit unless you enable --llm."
      echo "        For a deep pass later: truecourse analyze --llm --stash --no-skills"
    else
      warn "hook install failed"
    fi
  else
    ok "Skipped pre-commit hook (faster commits)"
  fi

else
  warn "truecourse not available — architecture step skipped"
fi

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
  "$PROJECT_ROOT/.claude/skills" \
  "$GLOBAL_SKILLS/agent-browser-src/skills" \
  "$GLOBAL_SKILLS/gsd-src/skills" \
  "$GLOBAL_SKILLS/vercel-skills-src/skills"
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





# ---------- H. Git hooks: self-updating graphs (interactive) ----------
echo -e "
${BLD}H. Self-updating graphs (git hooks)...${RST}"
echo
echo "  Estimates for a repo the size of Sterling (~600–2000 files):"
echo "  ┌─────────────────────────────────────────────────────────────────────────┐"
echo "  │ Hook set              │ When              │ Extra time / commit (approx) │"
echo "  │───────────────────────┼───────────────────┼─────────────────────────────│"
echo "  │ Graphify only         │ post-commit/      │ ~5–30s  (graph refresh)     │"
echo "  │                       │ post-checkout     │                             │"
echo "  │ CRG update            │ commit / Claude   │ ~2–15s  (incremental)       │"
echo "  │                       │ session hooks     │                             │"
echo "  │ TrueCourse --diff     │ pre-commit        │ ~10–60s+ (diff analyze)     │"
echo "  │ ALL THREE             │ every commit      │ ~20–90s+ (can feel slow)    │"
echo "  └─────────────────────────────────────────────────────────────────────────┘"
echo "  Notes:"
echo "  • Times vary with dirty files, CPU, and whether LLM is involved (TC LLM = minutes)."
echo "  • TrueCourse pre-commit is usually deterministic --diff (no big LLM bill)."
echo "  • Graphify keeps graphify-out fresh; CRG keeps .code-review-graph fresh."
echo

# --- Graphify: stay-fresh default YES ---
if command -v graphify &>/dev/null; then
  echo "  Graphify self-update (recommended): refresh knowledge graph on commit/branch switch."
  read -r -p "  Enable Graphify hooks so graph stays fresh? [Y/n] " gh
  gh=${gh:-Y}
  if [[ "$gh" =~ ^[Yy]$ ]]; then
    graphify hook install 2>/dev/null && echo "  ✔ Graphify hooks ON (self-updating graph)" || echo "  ⚠ graphify hook install failed"
  else
    echo "  ⚠ Graphify hooks OFF — run later: graphify extract . --update && graphify hook install"
  fi
else
  echo "  ⚠ graphify not installed — skip Graphify hooks"
fi

echo
echo "  Enable ALL heavy hooks at once? (CRG git refresh + Graphify + TrueCourse pre-commit)"
echo "  Y — maximum freshness; commits can take ~20–90s+ on large repos"
echo "  N — keep lighter defaults (Graphify choice above; no forced TrueCourse pre-commit) [default]"
read -r -p "  Enable CRG + Graphify + TrueCourse hooks together? [y/N] " allh
allh=${allh:-N}

if [[ "$allh" =~ ^[Yy]$ ]]; then
  echo "  → Installing full hook bundle..."
  if command -v graphify &>/dev/null; then
    graphify hook install 2>/dev/null && echo "  ✔ Graphify hooks" || echo "  ⚠ Graphify hooks failed"
  fi
  if command -v code-review-graph &>/dev/null; then
    code-review-graph install --platform claude-code 2>/dev/null || true
    code-review-graph build 2>/dev/null || echo "  ⚠ CRG build issues"
    echo "  ✔ CRG install/build attempted"
  fi
  if command -v truecourse &>/dev/null; then
    truecourse hooks install 2>/dev/null && echo "  ✔ TrueCourse pre-commit ON (~10–60s+/commit)" || echo "  ⚠ TrueCourse hooks failed"
  fi
  echo
  echo "  Full bundle ON. Expect slower commits; disable later if painful:"
  echo "    graphify hook uninstall"
  echo "    truecourse hooks uninstall"
else
  echo "  Skipped full triple-hook bundle (safer/faster commits)"
  echo "  Graphify stay-fresh = your answer above only."
  echo "  TrueCourse pre-commit remains off unless you enable it separately."
fi

# ----- Done -----
echo -e "\n${GRN}${BLD}"
echo "=============================================="
echo "  ✅  Setup complete"
echo "=============================================="
echo -e "${RST}"
echo "Stack:"
echo "  • code-review-graph  → daily coding, impact, token savings"
echo "  • TrueCourse
  • Graphify            → optional knowledge graph (global skill)
  • Graphify            → optional knowledge graph (global skill)         → architecture (cycles, layers, god modules)"
echo "  • Skills             → dynamic 1–3 per task (see CLAUDE.md)"
echo "  • CLI                → rg fd sg jq yq gh"
echo
echo "New users:  ./scripts/setup-claude.sh   OR   make setup-claude"
echo "Then: restart Claude Desktop → open project → NEW session"
echo

# ---------- H. Git hooks: self-updating graphs (interactive) ----------
echo -e "\n${BLD}H. Self-updating graphs (git hooks)...${RST}"
echo
echo "  Estimates for a repo the size of Sterling (~600–2000 files):"
echo "  ┌─────────────────────────────────────────────────────────────────────────┐"
echo "  │ Hook set              │ When              │ Extra time / commit (approx) │"
echo "  │───────────────────────┼───────────────────┼─────────────────────────────│"
echo "  │ Graphify only         │ post-commit/      │ ~5–30s  (graph refresh)     │"
echo "  │                       │ post-checkout     │                             │"
echo "  │ CRG update            │ commit / Claude   │ ~2–15s  (incremental)       │"
echo "  │                       │ session hooks     │                             │"
echo "  │ TrueCourse --diff     │ pre-commit        │ ~10–60s+ (diff analyze)     │"
echo "  │ ALL THREE             │ every commit      │ ~20–90s+ (can feel slow)    │"
echo "  └─────────────────────────────────────────────────────────────────────────┘"
echo "  Notes:"
echo "  • Times vary with dirty files, CPU, and whether LLM is involved (TC LLM = minutes)."
echo "  • TrueCourse pre-commit is usually deterministic --diff (no big LLM bill)."
echo "  • Graphify keeps graphify-out fresh; CRG keeps .code-review-graph fresh."
echo

# --- Graphify: stay-fresh default YES ---
if command -v graphify &>/dev/null; then
  echo "  Graphify self-update (recommended): refresh knowledge graph on commit/branch switch."
  read -r -p "  Enable Graphify hooks so graph stays fresh? [Y/n] " gh
  gh=${gh:-Y}
  if [[ "$gh" =~ ^[Yy]$ ]]; then
    graphify hook install 2>/dev/null && echo "  ✔ Graphify hooks ON (self-updating graph)" || echo "  ⚠ graphify hook install failed"
  else
    echo "  ⚠ Graphify hooks OFF — run later: graphify extract . --update && graphify hook install"
  fi
else
  echo "  ⚠ graphify not installed — skip Graphify hooks"
fi

echo
echo "  Enable ALL heavy hooks at once? (CRG git refresh + Graphify + TrueCourse pre-commit)"
echo "  Y — maximum freshness; commits can take ~20–90s+ on large repos"
echo "  N — keep lighter defaults (Graphify choice above; no forced TrueCourse pre-commit) [default]"
read -r -p "  Enable CRG + Graphify + TrueCourse hooks together? [y/N] " allh
allh=${allh:-N}

if [[ "$allh" =~ ^[Yy]$ ]]; then
  echo "  → Installing full hook bundle..."
  if command -v graphify &>/dev/null; then
    graphify hook install 2>/dev/null && echo "  ✔ Graphify hooks" || echo "  ⚠ Graphify hooks failed"
  fi
  if command -v code-review-graph &>/dev/null; then
    code-review-graph install --platform claude-code 2>/dev/null || true
    code-review-graph build 2>/dev/null || echo "  ⚠ CRG build issues"
    echo "  ✔ CRG install/build attempted"
  fi
  if command -v truecourse &>/dev/null; then
    truecourse hooks install 2>/dev/null && echo "  ✔ TrueCourse pre-commit ON (~10–60s+/commit)" || echo "  ⚠ TrueCourse hooks failed"
  fi
  echo
  echo "  Full bundle ON. Expect slower commits; disable later if painful:"
  echo "    graphify hook uninstall"
  echo "    truecourse hooks uninstall"
else
  echo "  Skipped full triple-hook bundle (safer/faster commits)"
  echo "  Graphify stay-fresh = your answer above only."
  echo "  TrueCourse pre-commit remains off unless you enable it separately."
fi
# ---------- I. Obsidian vault (human notes / backlinks — optional) ----------
echo -e "\n${BLD}I. Obsidian vault (human knowledge base)...${RST}"
echo "  Light optional vault for notes, architecture decisions, daily notes, Graphify export."
echo "  Complements: CRG (code impact), TrueCourse (violations), Graphify (code+docs graph)."
echo
echo "  Create Obsidian project vault? (default Y)"
echo "  Y — create docs/obsidian/ + README (recommended)"
echo "  N — skip (use global Obsidian vault only)"
read -r -p "  Create Obsidian vault? [Y/n] " obs
obs=${obs:-Y}
if [[ "$obs" =~ ^[Yy]$ ]]; then
  mkdir -p docs/obsidian
  cat > docs/obsidian/README.md << 'OBS'
# Sterling Obsidian Vault

## Purpose
- Human notes, architecture decisions, daily notes
- Graphify export target
- Backlinks and visual graph for project knowledge

## Folders
- `daily/` — daily notes
- `architecture/` — decisions, diagrams
- `graphs/` — exported from Graphify
OBS
  echo "  ✔ Obsidian vault created → docs/obsidian/"
else
  echo "  Skipped Obsidian project vault"
fi

# Ensure gitignore for Obsidian workspace files
grep -q ".obsidian" .gitignore 2>/dev/null || echo -e "\n# Obsidian\n.obsidian/\n" >> .gitignore
