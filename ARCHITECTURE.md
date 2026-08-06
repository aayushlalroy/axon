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
- `stage_skill(src)` — always stores as `<name>/SKILL.md` folder in hub
- `stage_principle(src)` / `stage_workflow(src)` — store as flat files
- `get_staged_items()` — returns all items in the hub
- `update_config_state()` — persist enabled/disabled state to `config.yaml`

### `cli.py`
- `_dest_name_for(name, adapter, item_type)` — computes the final filename inside target dir
- `_do_enable_link(src, target_dir, dest_name, adapter, item_type)` — creates the symlink with the correct strategy (whole folder vs SKILL.md only vs flat file)
- `_do_disable_link(target_dir, dest_name)` — removes the symlink

---

## State Management

State is tracked in `~/.axon/config.yaml`:

```yaml
agents:
  cursor:
    local:
      skills: ["ts-rules"]
      principles: ["always-types.md"]
  devin:
    local:
      skills: ["deploy"]
      workflows: ["pr-review.md"]
    global:
      skills: ["company-standards"]
```

`axon sync` reads this file and recreates any missing symlinks, making it safe to clone a project on a new machine and restore all links from config.

---

## Version & Release Flow

```
scripts/release.sh 0.3.0 --push
  ↓
bumps pyproject.toml version
inserts CHANGELOG.md entry
git commit + git tag v0.3.0
git push origin main + v0.3.0
  ↓
.github/workflows/release.yml fires
  ↓
GitHub Release created with CHANGELOG notes
  ↓
users: axon update
       or: bash <(curl -sSL …/install.sh)
```
