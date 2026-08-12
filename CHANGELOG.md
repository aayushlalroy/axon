# Changelog

## [2.0.0] — 2026-08-13

### Added
- **De-initialize Command (`axon deinit`)** — Permanently remove project-initialized agent directories and managed files with explicit safety warning prompt and `-y` flag.
- **Actionable Warning Messages & Agent Aliases** — Enhanced warnings across all commands to provide clear next steps (e.g. `Run 'axon agents' to see all supported agent IDs`, `Run 'axon init --agent <name>' to scaffold directories`), and added support for agent aliases (`antigravity` -> `gemini`, `cascade` -> `windsurf`, `claude-code` -> `claude`, `github-copilot` -> `copilot`).
- **Interactive Default Agents Configuration (`enabled_agents` & `axon setup`)** — Configure default managed frameworks during interactive installation (`install.sh`), `axon update`, or via `axon setup`.
- **Project Agent Directory Scoping** — CLI commands (`enable`, `disable`, `activate`, `deactivate`, `list`, `sync`) inspect project root and strictly scope operations to initialized agent directories. Re-running `axon init` is fully idempotent.
- **Multi-Agent CLI Option Permutations** — Flexible multi-agent targeting across all CLI commands using multiple `--agent` flags, comma-separated lists, and equals-sign syntax.

---

### Fixed
- **Multi-Type Disambiguation (`3) all` option)** — Fixed `axon enable` and `axon disable` when selecting `3) all` on multi-type staged items (e.g. staged as `skill` and `principle`). It now only targets the actual staged types for that item rather than blindly attempting non-existent types (`workflow`).

---

## [1.0.0] — 2026-08-12

### Added
- **Official v1.0.0 Production Release** of Axon — Universal Skill & Constitution Management System for AI coding agents.
- **Bulk Staging (`axon import`)** — stage entire repositories/assets trees from folder auto-scanning or `axon-import.yaml` manifests.
- **Un-staging & Lifecycle Deletion (`axon remove`)** — purge staged hub assets, symlinks, physical local overrides, and configuration state.
- **Auxiliary / Additional Files Support** — preserve non-primary skill assets (`schema-code-sync.md`, `CHECKS.md`, `CRITIQUE.md`, etc.), link them into flat-file agent directories (Cursor/Windsurf), and track shared dependencies in `config.yaml`.
- **Multi-Type Asset Staging** — stage assets as any combination of `skill`, `principle`, `workflow` with strict validation errors and interactive selection prompts.
- **Customizable Configuration System** — global `~/.axon/config.yaml` and project `axon-config.yaml` support for `defaults.name_source`, `defaults.scope`, and `defaults.ignore_patterns`.
- **Community AI Assets Link** — integrated starting guide for [github.com/aayushlalroy/ai-assets](https://github.com/aayushlalroy/ai-assets).
- **185 Unit, Integration & E2E Sandbox Matrix Tests** — 100% test pass rate.

---

## [0.3.0b1] — 2026-08-11 *(beta)*

### Added
- **`axon import` command** — bulk stage skills, principles, and workflows from directory auto-scanning or `axon-import.yaml` manifests.
- **`axon remove` command** — un-stage items, purge target symlinks across all agents, clean physical local file overrides from `activate`/`deactivate`, and clean `config.yaml` state.
- **Additional files support** — skill auxiliary files (e.g. `schema-code-sync.md`, `CHECKS.md`, `prompts/PROMPTS.md`) are preserved during staging, linked into flat-file agent target directories (Cursor/Windsurf), and tracked via a shared dependency reference registry in `config.yaml`.
- **Append file to skill** — `axon add path/to/extra.md --skill <skill_name>` appends additional files into existing staged skills.
- **Multi-type staging & disambiguation** — stage the same asset as any combination of `skill`, `principle`, `workflow`. `axon enable` validates explicit type prefixes and presents interactive selection when an item is staged under multiple types.
- **Global & project configuration system (`axon-config.yaml`)** — customize default name sources, target scope, and ignore rules. Documented in [`CONFIG.md`](./CONFIG.md).
- **Default ignore rules** — `README.md`, `INDEX.md`, `.DS_Store`, `.git*`, `*.tmp` ignored by default during staging and importing.
- Expanded test suite from 57 to 170 unit and integration tests.

---

## [0.2.0b1] — 2026-08-06 *(beta)*

> ⚠️ **Beta release** — APIs and behaviour may change before the stable `0.2.0` final.

### Added
- **Skill format awareness** — agents now declare `skill_format` in `agents.yaml`:
  - `folder_skill_md` (Devin, Claude, Gemini, Codex): symlinks the whole `<name>/SKILL.md` folder
  - `flat_mdc` (Cursor): symlinks `SKILL.md` as `<name>.mdc` in `.cursor/rules/`
  - `flat_md` (Windsurf): symlinks `SKILL.md` as `<name>.md` in `.windsurf/rules/`
  - `none` (Copilot): skills unsupported; only instruction files used
- **Workflow support** — `axon enable workflow`, `axon disable workflow`, `axon add --type workflow`
- **`axon version`** command — prints the installed package version
- **`axon update`** command — upgrades Axon in-place (`axon update --version v0.2.0` to pin)
- **`agents.yaml`** configuration registry — single source of truth for all agent paths
- **Global fallback** — `--global` automatically falls back to `--local` with a warning when the agent has no global directories (e.g. Windsurf)
- **Broken symlink replacement** — `enable` replaces dangling symlinks instead of failing
- **`scripts/release.sh`** — version bump + CHANGELOG + tag in one command
- **GitHub Actions** — CI runs tests on Python 3.9/3.11/3.12 × Ubuntu/macOS; release workflow creates GitHub Releases from tags
- Test suite grew from 6 → 57 tests

### Changed
- Skills in the staging hub (`~/.axon/skills/`) are **always** stored as `<name>/SKILL.md` folders (open AgentSkills standard), regardless of source file shape
- `axon add` now accepts `--type skill|principle|workflow` flag (skips interactive prompt)
- `install.sh` now requires Python ≥ 3.9, supports `--version` flag and `AXON_VERSION` env var
- `uninstall.sh` now supports `--keep-data` and `--purge` flags; safe in non-interactive shells
- `get_staged_items()` now returns skills, principles, **and** workflows
- `init_axon_dir()` creates `~/.axon/workflows/` directory

### Fixed
- Windsurf `init` no longer creates a `.windsurf/skills/` directory (Windsurf uses rules, not skills)
- `uninstall.sh` no longer crashes when piped from curl (interactive prompt now guarded)
- `scaffold_local_env` creates parent directories for file targets before touching them

---

## [0.1.0] — 2026-07-15

### Added
- Initial release of Axon CLI
- `axon init` — scaffold agent directories in a project
- `axon add` — interactively stage skills and principles into `~/.axon/`
- `axon enable` / `axon disable` — create/remove symlinks per agent
- `axon sync` — rebuild all symlinks from `config.yaml`
- `axon list` — show enabled items per agent
- `axon agents` — list all supported adapters
- Supported agents: Cursor, Claude Code, Gemini/Antigravity, Devin, Codex, Windsurf, GitHub Copilot
- `install.sh` / `uninstall.sh` one-liner scripts
