# Axon Configuration Guide (`axon-config.yaml`)

Axon allows you to customize all default behaviors, name extraction strategies, and ignore patterns using configuration files.

---

## Configuration File Locations

Axon looks for configuration settings in the following order (highest precedence first):
1. Project-level configuration file: `axon-config.yaml` or `axon.yaml` in the current working directory.
2. User-level configuration file: `~/.axon/config.yaml`.
3. Built-in defaults.

---

## Schema Overview

Here is a complete `axon-config.yaml` template:

```yaml
defaults:
  name_source: auto        # auto | frontmatter | folder | file
  scope: local             # local | global
  ignore_patterns:
    - "README.md"
    - "INDEX.md"
    - ".DS_Store"
    - "*.tmp"

import:
  name_source: auto        # auto | frontmatter | folder | file
  ignore_patterns:
    - "README.md"
    - "INDEX.md"
    - "AGENTS.md"

staging:
  ignore_readme: true      # Exclude README.md files during skill staging
```

---

## Configuration Attributes Reference

### `defaults.name_source`
* **Description**: Sets the default strategy used to derive item names when staging or enabling items.
* **Allowed Values**:
  * `auto` (Default): Uses YAML frontmatter `name:` property first. If missing, falls back to folder name (for directories) or file stem (for standalone files).
  * `frontmatter`: Reads YAML frontmatter `name:` property in `SKILL.md` or `.md` files.
  * `folder`: Uses directory name for skills, or file stem for principles/workflows.
  * `file`: Uses file stem of the primary file (`SKILL.md` stem or principle/workflow `.md` stem).

### `defaults.scope`
* **Description**: Default target scope when enabling, disabling, activating, or deactivating items without specifying `--global` or `--local`.
* **Allowed Values**: `local` (default), `global`.

### `defaults.ignore_patterns`
* **Description**: List of file names or glob patterns automatically ignored during staging (`axon add`) and bulk importing (`axon import`).
* **Default Values**:
  ```yaml
  - "README.md"
  - "INDEX.md"
  - ".DS_Store"
  - "*.tmp"
  ```
* **Behavior**: Files matching these patterns inside skill folders or source directories will not be staged as auxiliary/additional files or standalone items unless explicitly passed.

### `import.name_source`
* **Description**: Overrides `defaults.name_source` specifically for the `axon import` command.

### `import.ignore_patterns`
* **Description**: List of glob patterns ignored specifically during `axon import`.

### `staging.ignore_readme`
* **Description**: When set to `true`, `README.md` files inside skill folders are automatically ignored during staging.
* **Allowed Values**: `true` (default), `false`.
