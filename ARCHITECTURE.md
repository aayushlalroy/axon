# Axon Architecture

Axon is built on a **hub-and-spoke** model: a central staging hub (`~/.axon/`) stores every skill, principle, and workflow once. Agent-specific directories are populated via symbolic links, so an edit to the source is immediately reflected everywhere.

---

## Directory Structure

```
~/.axon/                    Central hub (machine-wide)
├── config.yaml             State: what is enabled where
├── skills/
│   └── <skill-name>/       ALWAYS a folder (AgentSkills standard)
│       ├── SKILL.md        Required: YAML frontmatter + instructions
│       ├── scripts/        Optional: helper scripts
│       └── references/     Optional: supplementary docs
├── principles/
│   └── <name>.md           Flat markdown file (always-on rules)
└── workflows/
    └── <name>.md           Flat markdown file (repeatable procedures)
```

```
your-project/               Per-project agent directories
├── .devin/
│   ├── skills/<name>/      → symlink to ~/.axon/skills/<name>
│   └── workflows/<name>.md → symlink to ~/.axon/workflows/<name>.md
├── .claude/
│   └── skills/<name>/      → symlink to ~/.axon/skills/<name>
├── .cursor/
│   └── rules/<name>.mdc    → symlink to ~/.axon/skills/<name>/SKILL.md
└── .windsurf/
    └── rules/<name>.md     → symlink to ~/.axon/skills/<name>/SKILL.md
```

---

## Skill Formats

Each agent declares a `skill_format` in `agents.yaml`. This drives all linking decisions:

| `skill_format` | Agents | Link target | Link name |
|---|---|---|---|
| `folder_skill_md` | Devin, Claude, Gemini, Codex | `~/.axon/skills/<name>` (whole folder) | `<name>` |
| `flat_mdc` | Cursor | `~/.axon/skills/<name>/SKILL.md` | `<name>.mdc` |
| `flat_md` | Windsurf | `~/.axon/skills/<name>/SKILL.md` | `<name>.md` |
| `none` | Copilot | (no skill files) | — |

Principles and workflows are always flat files; they are symlinked as `<name>.md` in the agent's rules or workflows directory.

---

## Key Components

### `agents.yaml`
Single source of truth for all agent paths. Defines:
- `skill_format` — linking strategy
- `local.skills` / `local.principles` / `local.workflows` — project-level target dirs
- `global.skills` / … — machine-wide target dirs (not all agents support this)
- `local.files` — flat instruction files to touch on `axon init` (e.g. `CLAUDE.md`, `AGENTS.md`)

### `adapters.py` — `AgentAdapter`
Loaded dynamically from `agents.yaml`. Provides:
- `uses_skill_folders` — True for `folder_skill_md`
- `supports_skills` — False for `skill_format: none`
- `get_skill_suffix()` — `.mdc`, `.md`, or `""` (folder format)
- `get_dir_paths(item_type, is_global)` — returns target directories
- `scaffold_local_env()` — creates all local dirs + touches flat files

### `core.py`
- `init_axon_dir()` — ensures `~/.axon/{skills,principles,workflows}/` exist
- `normalize_name(name)` — strips `.md` / `.mdc` extensions for unified base lookup
- `should_ignore_file(path)` — evaluates default (`README.md`, `INDEX.md`, `.DS_Store`) and custom ignore patterns
- `stage_skill(src)` — stores as `<name>/SKILL.md` folder in hub (copying all auxiliary files and subdirectories)
- `stage_principle(src)` / `stage_workflow(src)` — store as flat files
- `get_skill_additional_files(skill_path)` — returns non-primary auxiliary files in a skill
- `register_shared_additional_file()` / `unregister_shared_additional_file()` — reference counter tracking shared auxiliary files across enabled skills
- `remove_staged_item(item_name, item_type)` — purges staged hub files, symlinks, physical local overrides, and config state

### `cli.py`
- `_dest_name_for(name, adapter, item_type)` — computes the final filename inside target dir
- `_do_enable_item(src, target_dir, dest_name, adapter, item_type)` — creates symlinks for primary item and auxiliary files (for flat-file agents like Cursor/Windsurf)
- `_do_disable_item(target_dir, dest_name)` — removes symlinks and cleans shared auxiliary files
- `import_cmd` (`axon import`) — bulk stages skills/principles/workflows using `axon-import.yaml` or directory auto-scanning
- `remove_cmd` (`axon remove`) — un-stages items, purges target symlinks, local overrides, and config state

---

## State Management

State is tracked in `~/.axon/config.yaml`:

```yaml
agents:
  cursor:
    local:
      skills: ["ts-rules"]
      principles: ["always-types"]
  devin:
    local:
      skills: ["deploy"]
      workflows: ["pr-review"]
    global:
      skills: ["company-standards"]

shared_additional_files:
  "schema-code-sync.md":
    - "openapi-contract-first"
    - "pr-review-principal"
```

`axon sync` reads this file and recreates any missing symlinks, making it safe to clone a project on a new machine and restore all links from config.

---

## Version & Release Flow

```
scripts/release.sh 2.0.0 --push
  ↓
bumps pyproject.toml version
inserts CHANGELOG.md entry
git commit + git tag v2.0.0
git push origin main + v2.0.0
  ↓
.github/workflows/release.yml fires
  ↓
GitHub Release created with CHANGELOG notes
  ↓
users: axon update
       or: bash <(curl -sSL …/install.sh)
```

---

## Community Resources & Blog Posts

* 📦 **[ai-assets Repository](https://github.com/aayushlalroy/ai-assets)** — Official community repository containing production-ready skills, principles, and workflows.
* 📦 **[Axon Repository](https://github.com/aayushlalroy/axon)** — Official source code and documentation for Axon CLI.
* ✍️ **[Axon CLI Blog Post](https://www.roya2yush.com/writing/axon-ai-agent-skill-management)** — Deep dive into Axon's skill and constitution management system.
* ✍️ **[AI Assets Blog Post](https://www.roya2yush.com/writing/ai-assets-production-ready-agent-skills)** — Guide to production-ready agent skills and principles.
* 🧠 **[Skills, Principles & Workflows Architecture](https://www.roya2yush.com/writing/ai-agent-skills-principles-workflows-architecture)** — Architectural guide explaining how skills, principles, and workflows operate together.


