# Axon

**Axon** is a universal Skill & Constitution Management System for AI coding agents.

It provides a single CLI (`axon`) to manage, stage, and deploy **Skills** (on-demand task instructions), **Principles** (always-on coding rules), and **Workflows** across every major AI agent environment — Cursor, Claude Code, Gemini/Antigravity, Devin, Codex, Windsurf, and GitHub Copilot.

[![Tests](https://github.com/aayushlalroy/axon/actions/workflows/tests.yml/badge.svg)](https://github.com/aayushlalroy/axon/actions/workflows/tests.yml)
[![Version](https://img.shields.io/github/v/tag/aayushlalroy/axon?label=version)](https://github.com/aayushlalroy/axon/releases)

> 📖 **Deep-Dive Articles**: Read about [Axon's architecture and skill management system](https://www.roya2yush.com/writing/axon-ai-agent-skill-management) and how [skills, principles, and workflows fit together](https://www.roya2yush.com/writing/ai-agent-skills-principles-workflows-architecture).

---

## How it works

```
 ~/.axon/                         ← Central staging hub
 ├── skills/
 │   └── fast-format/             ← Skill (always a folder/SKILL.md)
 │       └── SKILL.md
 ├── principles/
 │   └── skill-attribution.md     ← Principle (flat .md file)
 └── workflows/
     └── pr-review.md             ← Workflow (flat .md file)

 your-project/
 ├── .devin/skills/fast-format/   ← symlink → ~/.axon/skills/fast-format
 ├── .claude/skills/fast-format/  ← symlink → ~/.axon/skills/fast-format
 └── .cursor/rules/fast-format.mdc ← symlink → ~/.axon/skills/fast-format/SKILL.md
```

Axon creates symlinks from your central hub (`~/.axon/`) into each agent's expected directory layout. Edit an asset once in `~/.axon/` and every project picks up the change automatically.

---

## Supported Agent IDs

Axon works natively with all major AI coding agents. Use these agent IDs when running targeted commands (`--agent <ID>`):

| Agent ID | Agent Name | Skills Format | Principles Format | Workflows Format | Global Scope Path |
|---|---|---|---|---|---|
| `cursor` | Cursor | `.cursor/rules/<name>.mdc` | `.cursor/rules/<name>.mdc` | — | `~/.cursor/rules/` |
| `claude` | Claude Code | `.claude/skills/<name>/SKILL.md` | `.claude/rules/<name>.md` | `.claude/commands/<name>.md` | `~/.claude/` |
| `gemini` | Gemini / Antigravity | `.agents/skills/<name>/SKILL.md` | `.agents/rules/<name>.md` | `.agents/workflows/<name>.md` | `~/.gemini/config/` |
| `devin` | Devin | `.devin/skills/<name>/SKILL.md` | `.devin/rules/<name>.md` | `.devin/workflows/<name>.md` | `~/.config/devin/` |
| `codex` | Codex | `.codex/skills/<name>/SKILL.md` | `.codex/rules/<name>.md` | `.codex/workflows/<name>.md` | `~/.codex/` |
| `windsurf` | Windsurf | `.windsurf/rules/<name>.md` | `.windsurf/rules/<name>.md` | `.windsurf/workflows/<name>.md` | — |
| `copilot` | GitHub Copilot | — *(unsupported)* | `.github/instructions/<name>.md` | — | — |

---

## Installation

### One-liner (recommended)

```bash
curl -sSL https://raw.githubusercontent.com/aayushlalroy/axon/main/install.sh | bash
```

Installs Axon into an isolated Python environment at `~/.axon-env` and links the binary to `~/.local/bin/axon`. Requires Python ≥ 3.9.

During installation, an interactive prompt configures your default managed agents (`enabled_agents`).

### Install a specific version

```bash
# Via environment variable:
AXON_VERSION=v1.1.0 bash <(curl -sSL https://raw.githubusercontent.com/aayushlalroy/axon/main/install.sh)

# Via flag:
bash install.sh --version v1.1.0
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

## Get Started

Depending on the agent framework or IDE you use (e.g. `cursor`, `claude`, `gemini`, `devin`), your agents require a **Principle** (always-on rule), a **Skill** (on-demand instruction), or a **Workflow** (step-by-step procedure).

Starting with a **Principle** is the fastest and cleanest way to begin because principles apply universally to keep agent behavior consistent across projects.

### Step 1: Add a Principle

If you don't have a principle file handy, you can fetch production-ready principles from the official community repository: [**ai-assets**](https://github.com/aayushlalroy/ai-assets).

For example, download the `skill-attribution` principle (which forces agents to log which tools/skills they used) and stage it into Axon:

```bash
# Fetch a pre-built principle from ai-assets
curl -sSL -O https://raw.githubusercontent.com/aayushlalroy/ai-assets/main/principles/skill-attribution.md

# Stage the principle into central hub (~/.axon/principles/)
axon add skill-attribution.md --type principle
```

### Step 2: Initialize Your Project & Enable the Principle

Navigate into your project repository, initialize Axon directory structures for your active agents, and enable the staged principle:

```bash
# Go to your project repository
cd /path/to/my-project

# Initialize agent folders for specific agent(s) or default configured agents
axon init --agent cursor
# or initialize all default agents:
axon init

# Enable the principle in your current project
axon enable principle skill-attribution
```

Axon automatically creates the required symlinks for all initialized agents in the project.

To temporarily turn off the principle in this project:
```bash
axon disable principle skill-attribution
```

### Step 3: Add and Enable a Skill

Next, add an on-demand **Skill**. You can grab a skill from [ai-assets](https://github.com/aayushlalroy/ai-assets) or use a local skill directory:

```bash
# Stage a skill (a folder containing SKILL.md or a standalone .md file)
axon add path/to/clarify-first --type skill

# Enable the skill in your project
axon enable skill clarify-first

# Disable the skill when no longer needed
axon disable skill clarify-first
```

### Step 4: Authoring Your Own Custom Principles & Skills

Creating custom rules and skills tailored to your workflow is straightforward:

#### Adding your own custom Principle:
Create a plain Markdown file defining your rule (e.g., `no-console-log.md`):

```markdown
# No Console Logs
NEVER leave `console.log` statements in production code. Use the logger service instead.
```

Stage it with `axon add`:
```bash
axon add no-console-log.md --type principle
```

#### Adding your own custom Skill:
Create a skill directory with a `SKILL.md` file (e.g. `my-tester/SKILL.md`):

```markdown
---
name: my-tester
description: Run end-to-end tests and output a summary report.
---
# E2E Testing Instructions
Run `npm test` and verify that all integration suites pass cleanly.
```

Stage it with `axon add`:
```bash
axon add my-tester/ --type skill
```

Now enable your custom assets anytime in any project using `axon enable`.

### Step 5: Understanding Asset States

Axon manages assets through clear lifecycle states:

```
┌───────────────┐     axon enable      ┌───────────────┐
│               ├─────────────────────►│               │
│    STAGED     │                      │    ENABLED    │
│  (~/.axon/)   │◄─────────────────────┤  (symlinked)  │
│               │     axon disable     └───────┬───────┘
└───────┬───────┘                              │
        │                                      │ axon activate
        │ axon activate                        ▼
        ▼                              ┌───────────────┐
┌───────────────┐                      │   ACTIVATED   │
│   ACTIVATED   ├─────────────────────►│  (local file  │
│  (global/auto)│                      │   override)   │
└───────────────┘                      └───────────────┘
```

* **Staged (`axon add`)**: Stored centrally in `~/.axon/`. Ready for use across any project on your machine.
* **Enabled (`axon enable`)**: Active in the current project. Axon creates symlinks in the agent's target folder pointing back to `~/.axon/`.
* **Disabled (`axon disable`)**: Symlinks are safely removed from the current project. The asset remains intact in `~/.axon/`.
* **Activated (`axon activate`)**: Configures auto-invocation or creates an un-linked local file override for standalone editing.
* **Deactivated (`axon deactivate`)**: Reverts an activated override back to a managed symlink.

### Step 6: Bulk Importing Assets (`axon import`)

Instead of adding assets one by one, you can import an entire repository or assets folder (such as [ai-assets](https://github.com/aayushlalroy/ai-assets)) in a single command using `axon import`:

```bash
# Clone the community AI Assets repository
git clone https://github.com/aayushlalroy/ai-assets.git
cd ai-assets

# Bulk-import all skills, principles, and workflows into ~/.axon/
axon import . --config axon-import.yaml
```

Once imported, all community assets are staged in `~/.axon/`. You can now run `axon enable` in any project to activate individual skills or principles as needed!

---

## Quick Commands Reference

| Command | Description |
|---|---|
| `axon setup` | Interactively configure default managed agents |
| `axon version` | Display installed version |
| `axon update [--version TAG]` | Upgrade Axon CLI in-place |
| `axon agents` | List all supported agent IDs and target formats |
| `axon init [--agent NAME …]` | Scaffold agent directories in current project |
| `axon deinit [--agent NAME …] [-y]` | Safely remove project agent directories and managed files |
| `axon add PATH [--type TYPE …] [--name NAME] [--skill NAME]` | Stage a file/folder or append files to an existing skill |
| `axon import [PATH] [--config FILE] [--name-source STRATEGY] [--ignore GLOBS]` | Bulk stage skills, principles, and workflows from folder or manifest |
| `axon enable [TYPE] NAME [--agent NAME] [--global]` | Enable a staged asset (symlink into project or global agent directory) |
| `axon disable [TYPE] NAME [--agent NAME] [--global]` | Disable an asset (remove target symlink) |
| `axon activate [TYPE] NAME` | Enable auto-invocation or convert symlink to local physical override |
| `axon deactivate [TYPE] NAME` | Revert physical local override back to managed symlink |
| `axon remove [TYPE] NAME… [-y]` | Un-stage item(s), purge symlinks, local overrides, and config state |
| `axon list [--all] [--agent NAME]` | List enabled or all staged assets |
| `axon sync` | Hard rebuild all symlinks from `config.yaml` state |

---

## 🔍 In-Depth Architecture & Advanced Reference

### 1. Agent Directory Scoping & Presence Rules

Axon enforces strict scoping to ensure project repositories remain clean and only contain directories for agents you actually use.

* **Project Agent Detection**: When you run commands like `axon enable`, `axon disable`, `axon activate`, `axon deactivate`, `axon list`, or `axon sync` without an explicit `--agent` flag, Axon inspects your project root to see which agents have initialized folders (e.g. `.cursor/rules`, `.claude/skills`, `.agents/skills`, `.devin/skills`, `.codex/skills`, `.windsurf/rules`, `.github/instructions`).
* **Un-initialized Directory Safety**: If you ran `axon init --agent cursor` in a project, running `axon enable skill my-skill` will **only** create symlinks inside `.cursor/rules/my-skill.mdc`. It will **never** automatically create `.claude/`, `.devin/`, `.windsurf/`, or other un-initialized directories.
* **Idempotent Initialization**: Re-running `axon init --agent cursor` on a project that already has `.cursor/rules` will gracefully detect existing directories and skip without erroring or overwriting your files.
* **Explicit Agent Target Warning**: If you explicitly pass `--agent windsurf` to `axon enable` in a repository where Windsurf directories have not been created, Axon logs a helpful warning: `Warning: Agent 'windsurf' is not initialized in this project. Run 'axon init --agent windsurf' first.`

### 2. Default Managed Agents Configuration (`enabled_agents`)

You can control which agents `axon init` scaffolds by default when no `--agent` flag is passed.

* **Configuration Key**: `enabled_agents` in `~/.axon/config.yaml`.
* **Interactive Setup**: Run `axon setup` or re-run `axon update` to configure your preferred default agents:
  ```
  Which agents do you want Axon to manage by default?
    1. gemini (antigravity)
    2. cursor
    3. devin
    4. windsurf
    5. codex
    6. copilot
  Enter what all numbers do you want comma-separated no whitespace [Default: 1,2,3,4,5,6]: 1,2,3,4,6
  ```
* **Config File Schema (`~/.axon/config.yaml`)**:
  ```yaml
  enabled_agents:
    - gemini
    - cursor
    - devin
    - windsurf
    - copilot
  ```
* When `axon init` runs without `--agent`, it checks `enabled_agents` and only scaffolds directories for those configured frameworks.

### 3. Multi-Agent Option Permutations (`--agent`)

All commands supporting agent targeting (`init`, `enable`, `disable`, `activate`, `deactivate`, `list`) accept flexible multi-agent flag syntax:

* **Multiple Flags**:
  ```bash
  axon init --agent cursor --agent devin
  axon enable skill my-skill --agent cursor --agent devin
  ```
* **Comma-Separated Values**:
  ```bash
  axon init --agent cursor,devin,claude
  axon enable skill my-skill --agent cursor,devin
  ```
* **Equals-Sign Syntax**:
  ```bash
  axon init --agent=cursor --agent=devin
  ```
* **Resilient Execution**: Multi-agent operations process each requested agent independently. If an agent emits a warning (e.g., Windsurf does not support global skills), Axon continues processing all remaining targeted agents cleanly.

### 4. Hard Reset with `axon sync`

`axon sync` performs a hard reset of your project symlinks based on `~/.axon/config.yaml` and the project's initialized agent set.

* Iterates over enabled skills, principles, and workflows recorded in `config.yaml`.
* Validates that staged source files exist in `~/.axon/`.
* Re-links symlinks into initialized local agent folders.
* Cleans up stale symlinks and compiles combined principle target files (`.cursorrules`, `CLAUDE.md`, `AGENTS.md`, etc.).

---

## Configuration & Settings Guide

Axon supports customizable configuration globally via `~/.axon/config.yaml` or per project via `axon-config.yaml` (and `axon-import.yaml`). For a complete YAML schema breakdown, see [`CONFIG.md`](./CONFIG.md).

### How to Change Settings

#### 1. Machine-Wide Global Defaults (`~/.axon/config.yaml`)
Add a `defaults:` block to `~/.axon/config.yaml` to customize global defaults across all projects:

```yaml
enabled_agents:
  - gemini
  - cursor
  - devin
  - windsurf
  - codex
  - copilot

defaults:
  # Default name extraction strategy: auto | frontmatter | folder | file
  name_source: auto

  # Default target scope: local | global
  scope: local

  # Default files/globs to ignore when staging or importing
  ignore_patterns:
    - "README.md"
    - "INDEX.md"
    - ".DS_Store"
    - "*.tmp"
    - "*.draft.md"
```

#### 2. Project-Level Configuration (`axon-config.yaml`)
Place an `axon-config.yaml` in your project root to override settings for that specific repository. See [`axon-config.yaml.sample`](./axon-config.yaml.sample).

#### 3. Bulk Import Manifests (`axon-import.yaml`)
Configure `axon import` settings using `axon-import.yaml` or pass a custom manifest via `--config <path>`:

```yaml
name_source: folder
ignore:
  - "*.draft.md"
  - "PRIVATE.md"
skills:
  - path: skills/spring-startup-doctor
    name: spring-startup-doctor
principles:
  - path: principles/claim-tagging.md
```

---

## Community Assets & Articles

Explore pre-built, production-ready AI skills, principles, and workflows, along with articles on AI agent architecture:

* 📦 **[ai-assets Repository](https://github.com/aayushlalroy/ai-assets)** — Official community repository containing production-ready skills, principles, and workflows.
* 📦 **[Axon Repository](https://github.com/aayushlalroy/axon)** — Official source code and documentation for Axon CLI.
* ✍️ **[Axon CLI Blog Post](https://www.roya2yush.com/writing/axon-ai-agent-skill-management)** — Deep dive into Axon's skill and constitution management system.
* ✍️ **[AI Assets Blog Post](https://www.roya2yush.com/writing/ai-assets-production-ready-agent-skills)** — Guide to production-ready agent skills and principles.
* 🧠 **[Skills, Principles & Workflows Architecture](https://www.roya2yush.com/writing/ai-agent-skills-principles-workflows-architecture)** — Architectural guide explaining how skills, principles, and workflows operate together.

---

## Documentation Navigation Index

- 📘 **[CONFIG.md](./CONFIG.md)** — Complete configuration schema and settings reference (`axon-config.yaml`, `axon-import.yaml`).
- 🏗️ **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Technical hub-and-spoke architecture, linking strategies, and agent adapters.
- 📜 **[CHANGELOG.md](./CHANGELOG.md)** — Full version history, beta notes, and release logs.
- 🤖 **[AI_CONTEXT.md](./AI_CONTEXT.md)** — Architectural notes and instructions for AI agents modifying Axon.
- 📋 **[axon-config.yaml.sample](./axon-config.yaml.sample)** — Sample project & global configuration file.
- 📋 **[axon-import.yaml.sample](./axon-import.yaml.sample)** — Sample bulk import manifest.

---

## Releasing a new version (maintainers)

```bash
bash scripts/release.sh 2.0.0 --push
```

This bumps `pyproject.toml`, inserts a CHANGELOG entry, commits, tags `v2.0.0`, and pushes. GitHub Actions then automatically creates a GitHub Release with the CHANGELOG notes.

See [`CHANGELOG.md`](./CHANGELOG.md) for the full history.

---

## License

MIT © Aayush Lal Roy
