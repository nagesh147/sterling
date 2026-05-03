# Sterling Workspace — Claude AI Setup

A smart shell environment that injects the right context into every Claude session.
Skills, memory, and project graph are loaded automatically — you just run `claude`.

---

## One-Time Setup

Do this once. Never again.

```bash
# 1. Install skills (clones all 8 repos)
bash install-skills.sh

# 2. Load the new config
source ~/.bashrc

# 3. Verify everything landed
skills-check
```

`skills-check` will show a table like this:

```
SKILL                        STRAT   RAW    SMART  VIBE
─────────────────────────────────────────────────────────
✔ superpowers                full    48L    48L    48L
✔ frontend-design            full    43L    43L    43L
✔ ui-ux-pro-max-skill        full    38L    38L    38L
✔ claude-mem                 rules   22L    8L     8L
✔ awesome-claude-code        rules   31L    12L    12L
✔ code-review                rules   19L    9L     9L
✘ security-review                    not installed
✘ gstack                             not installed
```

- `full` — command/pattern skills. Loaded with descriptions so Claude knows *when* and *why* to use them.
- `rules` — rule-list skills. Directive lines only. No prose needed.
- `✘` — not installed. Run `bash install-skills.sh` to fix.

---

## Commands

| Command | Alias | Use for |
|---|---|---|
| `claude vibe` | `cv` | New projects, UI work, vibe coding |
| `claude smart` | `cs` | Existing projects, focused work |
| `claude ultra` | `cu` | Deep work, full codebase context |
| `claude` | — | Default — runs verify script if present |
| `ctx-inspect vibe` | — | See exactly what tokens are sent |
| `skills-check` | — | Check skill install status |
| `reload` | — | Reload bashrc after edits |

---

## New Project

Starting from scratch — no git history, no graph yet.

```bash
mkdir my-app && cd my-app
git init

# Start Claude in vibe mode
cv
```

**What vibe mode does for a new project:**

- Loads: `superpowers` `/plan /tdd /agents` with full descriptions
- Loads: `frontend-design` + `ui-ux-pro-max-skill` with full design rules
- Loads: `claude-mem` + `awesome-claude-code` as lean rule sets
- Skips: `code-review`, `security-review`, `gstack` — wrong phase
- Skips: graph — nothing useful in a fresh repo
- Loads: last 20 lines of `~/.claude/memory.md` — your persistent decisions

**Estimated tokens before your prompt: ~705**

**Recommended first prompt for a new project:**

```
/plan [describe what you're building]
```

Claude will generate a step-by-step plan before writing any code.
This is the `superpowers` `/plan` command — it needs its description
to work correctly, which is why `superpowers` is loaded as `full`.

---

## Existing Project

Project has commits, a graph, established patterns.

```bash
cd my-app

# Focused work — god nodes only, minimal context
cs

# Deep work — full graph, all context
cu
```

**What smart mode does for an existing project:**

- Detects your file types and loads matching skills automatically
- `.tsx/.jsx/tailwind` present → adds `frontend-design` + `ui-ux-pro-max-skill`
- `.ts/.js` present → adds `code-review` + `awesome-claude-code`
- `docker/prisma/k8s` present → adds `gstack`
- `auth/jwt/crypto` present → adds `security-review`
- Injects god nodes (most-imported files) from graph — the files Claude needs to know about
- Loads your persistent memory

**Estimated tokens before your prompt:**

| Mode | Skills | Graph | Memory | Total |
|---|---|---|---|---|
| `cv` new project | ~54L | 0L | ~6L | **~705 tok** |
| `cs` existing | ~54L | 30L | ~6L | **~900 tok** |
| `cu` existing | ~80L | 100L | ~6L | **~1600 tok** |

---

## Vibe Coding Flow

Best workflow for building something fast.

```bash
# Step 1 — new project
mkdir my-saas && cd my-saas && git init
cv

# Step 2 — in Claude, plan first
/plan Build a SaaS dashboard with auth, billing, and analytics

# Step 3 — implement in parallel
/agents

# Step 4 — after first features land, commit and switch to smart
git add . && git commit -m "initial"
cs

# Step 5 — review before any merge
/review

# Step 6 — before shipping auth
/sec-review
```

---

## Modes Reference

### `cv` — vibe mode
**Use when:** starting a project, building UI, creative work, prototyping.

Skill set is fixed regardless of file patterns:
```
superpowers (full) + frontend-design (full) + ui-ux-pro-max-skill (full)
claude-mem (rules) + awesome-claude-code (rules)
```
Graph skipped on new projects (< 5 commits). Loaded on existing ones (god nodes, 20L).

### `cs` — smart mode
**Use when:** working inside an existing codebase, focused feature work.

Skills detected from your file types. Graph: god nodes only (30L).
Enough context to understand the codebase shape without token overload.

### `cu` — ultra mode
**Use when:** complex refactors, debugging deep issues, architecture decisions.

All matching skills loaded at higher caps. Full graph report (100L).
Use sparingly — higher token cost means less budget for your actual prompt.

### `claude` — verify mode (default)
**Use when:** you have a `claude-verify.sh` in your project or `~/Sterling/`.

Passes context to your verify script instead of Claude directly.
Falls back to vibe mode if no verify script found.

---

## Persistent Memory

`claude-mem` writes to `~/.claude/memory.md` automatically during sessions.

The setup injects the **last 20 lines** into every context build.
Most recent decisions = most relevant = recency-weighted injection.

**What to store in memory:**
```
2024-01-15: Using Prisma over raw SQL — type safety across team
2024-01-15: JWT 15min expiry, refresh tokens in Redis
2024-01-16: No `any` in TypeScript — ESLint rule enforced
2024-01-16: Component library is shadcn/ui — do not add others
```

Memory loads in `cv`, `cs`, and `cu`. Never in `verify` (verify script owns its own context).

---

## Token Inspector

See exactly what gets sent to Claude before your prompt:

```bash
ctx-inspect vibe     # new project flow
ctx-inspect smart    # existing project flow
ctx-inspect ultra    # full context flow
```

Output shows per-skill lines, section totals, and estimated token count.
Use this after `skills-check` to confirm injection is working correctly.

---

## Maintenance

```bash
# Update all skill repos (run weekly or when output feels stale)
bash install-skills.sh update

# Or add to cron — runs every Sunday 3am
# 0 3 * * 0 bash ~/install-skills.sh update >> ~/.claude/skill-update.log 2>&1

# After updating, reload
reload
```

---

## Troubleshooting

**Skills show `✘` in skills-check**
```bash
bash install-skills.sh        # re-run install
skills-check                  # verify again
```

**Skills show `0L injected`**

The skill's SKILL.md headings don't match extraction patterns.
Check what's in the file:
```bash
cat ~/.claude/skills/skill-name/SKILL.md | head -40
```

**Context feels wrong / Claude ignoring skills**

Check what's actually being sent:
```bash
ctx-inspect smart
```

If `<s>` block is empty, the skill files aren't resolving.
Common cause: monorepo clone where skill lives in a subdirectory.
Fix: add to `SKILL_SUBDIR_MAP` in `~/.bashrc`.

**`ctx inject: unknown`**

Run `cs` once — this triggers the `--system` flag detection.
Result is cached for the session.

**Graph shows `–` (bypassed)**

`graphify` either isn't installed or failed.
The rest of the setup works fine without it — you just lose god-node context.
Install graphify from your Sterling setup to restore it.
