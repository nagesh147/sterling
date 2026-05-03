#!/usr/bin/env bash
# install-skills.sh — Clone or update all Sterling workspace skills
#
# Usage:
#   bash install-skills.sh          # install / update all
#   bash install-skills.sh update   # same (explicit)
#   bash install-skills.sh status   # check install state without cloning

set -euo pipefail

SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

# Format: "repo_url  target_dirname"
# Tab-separated for clean parsing
declare -a SKILLS=(
    "https://github.com/obra/superpowers.git                              superpowers"
    "https://github.com/anthropics/skills.git                            frontend-design"
    "https://github.com/thedotmack/claude-mem.git                        claude-mem"
    "https://github.com/anthropics/claude-code.git                       code-review"
    "https://github.com/anthropics/claude-code-security-review.git       security-review"
    "https://github.com/garrytan/gstack.git                              gstack"
    "https://github.com/hesreallyhim/awesome-claude-code.git               awesome-claude-code"
    "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git               ui-ux-pro-max-skill"
)

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m' GRN='\033[0;32m' YLW='\033[0;33m'
CYN='\033[0;36m' BLD='\033[1m'    RST='\033[0m'

print_header() {
    echo -e "\n${CYN}${BLD}Sterling Skill Manager${RST}  →  ${BLD}$SKILLS_DIR${RST}\n"
}

# ── Status-only mode ──────────────────────────────────────────────────────────
cmd_status() {
    print_header
    local ok=0 warn=0 miss=0
    for entry in "${SKILLS[@]}"; do
        local url name
        read -r url name <<< "$entry"
        local dir="$SKILLS_DIR/$name"
        if [[ -d "$dir/.git" ]]; then
            local entry_file=""
            for f in "$dir"/{SKILL,README,skill,index}.md; do
                [[ -f "$f" ]] && entry_file="$f" && break
            done
            if [[ -n "$entry_file" ]]; then
                local branch
                branch=$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
                echo -e "  ${GRN}✔${RST}  ${BLD}$name${RST}  [branch: $branch]  →  $(basename "$entry_file")"
                (( ok = ok + 1 ))
            else
                echo -e "  ${YLW}⚠${RST}  ${BLD}$name${RST}  cloned but no SKILL.md / README.md found"
                (( warn = warn + 1 ))
            fi
        else
            echo -e "  ${RED}✘${RST}  ${BLD}$name${RST}  not installed"
            (( miss = miss + 1 ))
        fi
    done
    echo -e "\n  ${GRN}${ok} ok${RST}  ${YLW}${warn} warnings${RST}  ${RED}${miss} missing${RST}\n"
    [[ $miss -gt 0 ]] && echo -e "  Run ${BLD}bash install-skills.sh${RST} to install missing skills.\n"
}

# ── Install / update mode ─────────────────────────────────────────────────────
cmd_install() {
    print_header
    mkdir -p "$SKILLS_DIR"

    local ok=0 updated=0 failed=0

    for entry in "${SKILLS[@]}"; do
        local url name
        read -r url name <<< "$entry"
        local dir="$SKILLS_DIR/$name"

        echo -ne "  ${CYN}→${RST}  ${BLD}$name${RST} ... "

        if [[ -d "$dir/.git" ]]; then
            # Already cloned — pull latest
            if git -C "$dir" pull --ff-only --quiet 2>/dev/null; then
                echo -e "${GRN}updated${RST}"
                (( updated = updated + 1 ))
            else
                echo -e "${YLW}up to date (or conflicts — check manually)${RST}"
                (( ok = ok + 1 ))
            fi
        else
            # Fresh clone
            if git clone --depth=1 --quiet "$url" "$dir" 2>/dev/null; then
                echo -e "${GRN}installed${RST}"
                (( ok = ok + 1 ))
            else
                echo -e "${RED}FAILED — check URL or network${RST}"
                (( failed = failed + 1 ))
            fi
        fi
    done

    echo -e "\n  ${GRN}${ok} installed  ${updated} updated${RST}  ${RED}${failed} failed${RST}\n"

    if [[ $failed -gt 0 ]]; then
        echo -e "  ${YLW}Some installs failed. Repos may be private or URLs may have changed.${RST}"
        echo -e "  Clone manually into: ${BLD}$SKILLS_DIR/<skill-name>${RST}\n"
        exit 1
    fi

    echo -e "  Run ${BLD}skills-check${RST} in your shell to verify injection.\n"
}

# ── Entry point ───────────────────────────────────────────────────────────────
case "${1:-install}" in
    status)         cmd_status ;;
    install|update) cmd_install ;;
    *)
        echo "Usage: bash install-skills.sh [install|update|status]"
        exit 1
        ;;
esac