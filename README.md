# Axon

**Axon** is a universal Skill & Constitution Management System for AI coding agents.

It provides a single CLI (`axon`) to manage, stage, and deploy **Skills** (on-demand task instructions) and **Principles** (always-on coding rules) across every major AI agent environment — Cursor, Claude Code, Gemini/Antigravity, Devin, Codex, Windsurf, and GitHub Copilot.

[![Tests](https://github.com/aayushlalroy/axon/actions/workflows/tests.yml/badge.svg)](https://github.com/aayushlalroy/axon/actions/workflows/tests.yml)
[![PyPI version](https://img.shields.io/pypi/v/axon-cli)](https://pypi.org/project/axon-cli/)

---

## How it works

```
 ~/.axon/                         ← Central staging hub
 ├── skills/
 │   └── fast-format/             ← Skill (always a folder/SKILL.md)
 │       └── SKILL.md
 ├── principles/
 │   └── no-comments.md           ← Principle (flat .md file)
 └── workflows/
     └── pr-review.md             ← Workflow (flat .md file)

 your-project/
 ├── .devin/skills/fast-format/   ← symlink → ~/.axon/skills/fast-format
 ├── .claude/skills/fast-format/  ← symlink → ~/.axon/skills/fast-format
 └── .cursor/rules/fast-format.mdc ← symlink → ~/.axon/skills/fast-format/SKILL.md
```

Axon creates symlinks from your central hub into each agent's expected directory layout. Edit a skill once in `~/.axon/` and every project picks up the change automatically.

---

## Features

| Feature | Description |
|---|---|
| **Universal hub** | All skills, principles, and workflows live in `~/.axon/`. Access from any project. |
| **Agent-aware linking** | Each agent gets the exact file layout it expects (folder/SKILL.md vs flat .mdc vs flat .md). |
| **Per-agent formats** | Cursor → `.mdc`, Windsurf → `.md`, Devin/Claude/Gemini/Codex → `folder/SKILL.md`. |
| **Local & global scope** | Enable per-project (`--local`) or machine-wide (`--global`). |
| **Workflow support** | Stage and deploy repeatable step-by-step workflows alongside skills. |
| **In-place updates** | `axon update` upgrades itself without reinstalling. |

---

## Supported Agents

| Agent | Skills format | Principles | Workflows | Global? |
|---|---|---|---|---|
| **Cursor** | `.cursor/rules/<name>.mdc` | `.cursor/rules/<name>.mdc` | — | `~/.cursor/rules/` |
| **Claude Code** | `.claude/skills/<name>/SKILL.md` | `.claude/rules/<name>.md` | `.claude/commands/<name>.md` | `~/.claude/` |
| **Gemini/Antigravity** | `.agents/skills/<name>/SKILL.md` | `.agents/rules/<name>.md` | `.agents/workflows/<name>.md` | `~/.gemini/config/` |
| **Devin** | `.devin/skills/<name>/SKILL.md` | `.devin/rules/<name>.md` | `.devin/workflows/<name>.md` | `~/.config/devin/` |
| **Codex** | `.codex/skills/<name>/SKILL.md` | `.codex/rules/<name>.md` | `.codex/workflows/<name>.md` | `~/.codex/` |
| **Windsurf** | `.windsurf/rules/<name>.md` | `.windsurf/rules/<name>.md` | `.windsurf/workflows/<name>.md` | — |
| **GitHub Copilot** | — (not supported) | `.github/instructions/<name>.md` | — | — |

---

## Installation

### One-liner (recommended)

```bash
curl -sSL https://raw.githubusercontent.com/aayushlalroy/axon/main/install.sh | bash
```

Installs Axon into an isolated Python venv at `~/.axon-env` and links the binary to `~/.local/bin/axon`. Requires Python ≥ 3.9 and no other dependencies.

### Install a specific version

```bash
# Via env var:
AXON_VERSION=v0.2.0 bash <(curl -sSL https://raw.githubusercontent.com/aayushlalroy/axon/main/install.sh)

# Via flag:
bash install.sh --version v0.2.0
```

### Via pipx (alternative)

```bash
pipx install git+https://github.com/aayushlalroy/axon.git
```

### From source

```bash
git clone https://github.com/aayushlalroy/axon.git
cd axon
pip install -e .
```

---

## Updating

```bash
axon update                    # update to latest
axon update --version v0.2.0   # update to a specific version
```

Or re-run the install script — it upgrades in-place.

---

## Uninstallation

```bash
curl -sSL https://raw.githubusercontent.com/aayushlalroy/axon/main/uninstall.sh | bash

# Flags:
#   --keep-data   never ask about ~/.axon (keep it)
#   --purge       remove ~/.axon without asking
```

---

## Quick Start

```bash
# 1. Initialize your project
cd your-project
axon init                          # scaffolds dirs for all agents
axon init --agent devin --agent claude  # or just specific agents

# 2. Stage a skill (can be a .md file or a folder containing SKILL.md)
axon add path/to/my-skill.md --type skill
axon add path/to/my-skill-folder  --type skill

# 3. Stage a principle (always-on rule)
axon add path/to/coding-style.md --type principle

# 4. Stage a workflow
axon add path/to/pr-review.md --type workflow

# 5. Enable for the current project
axon enable my-skill               # auto-detects type; all agents
axon enable skill my-skill --agent cursor   # specific agent
axon enable principle coding-style
axon enable workflow pr-review --agent devin

# 6. Enable globally (machine-wide)
axon enable my-skill --global

# 7. Disable
axon disable my-skill
axon disable skill my-skill --agent cursor

# 8. View status
axon list                          # enabled items per agent
axon list --all                    # everything staged

# 9. Rebuild all symlinks from config (recovery)
axon sync
```

---

## Commands Reference

| Command | Description |
|---|---|
| `axon version` | Show installed version |
| `axon update [--version TAG]` | Update Axon in-place |
| `axon agents` | List supported agents with their skill formats |
| `axon init [--agent NAME …]` | Scaffold agent directories in the current project |
| `axon add PATH [--type TYPE …] [--name NAME] [--skill NAME]` | Stage an item or append an additional file to an existing skill |
| `axon import [PATH] [--config FILE] [--name-source STRATEGY] [--ignore GLOBS] [--dry-run]` | Bulk stage items into `~/.axon/` from a folder or `axon-import.yaml` |
| `axon enable [TYPE] NAME [--agent NAME] [--global]` | Enable a staged item (with disambiguation if multi-type) |
| `axon disable [TYPE] NAME [--agent NAME] [--global]` | Disable (remove symlink and shared auxiliary files) |
| `axon remove [TYPE] NAME… [-y]` | Un-stage item(s), purge symlinks, local overrides, and config state |
| `axon activate [TYPE] NAME` | Enable auto-invocation (or create local override) |
| `axon deactivate [TYPE] NAME` | Disable auto-invocation |
| `axon list [--all] [--agent NAME]` | List enabled or all staged items with additional files |
| `axon sync` | Hard rebuild all symlinks from `config.yaml` |

---

## Configuration & Ignore Rules

Axon supports customizable global/project configuration via `axon-config.yaml` (or `~/.axon/config.yaml`). See [`CONFIG.md`](./CONFIG.md) for full details.

- **Default Ignores**: `README.md`, `INDEX.md`, `.DS_Store`, `.git*`, `*.tmp` are ignored by default when staging skills or running `axon import`.
- **Sample Import Manifest**: See [`axon-import.yaml.sample`](./axon-import.yaml.sample) for bulk import configurations.
- **Sample Config**: See [`axon-config.yaml.sample`](./axon-config.yaml.sample) for configurable defaults.

---

## Releasing a new version (maintainers)

```bash
bash scripts/release.sh 0.3.0 --push
```

This bumps `pyproject.toml`, inserts a CHANGELOG entry, commits, tags `v0.3.0`, and pushes. GitHub Actions then automatically creates a GitHub Release with the CHANGELOG notes.

See [`CHANGELOG.md`](./CHANGELOG.md) for the full history.

---

## Architecture

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the hub-and-spoke design and how `AgentAdapter` drives different linking strategies per agent.

---

## License

MIT © Aayush Lal Roy
