# Axon Architecture

Axon is built around a centralized hub-and-spoke model to resolve the impedance mismatch between different AI agent ecosystems.

## Directory Structure
- `~/.axon/`: The global hub. 
  - `config.yaml`: State tracking for what is enabled where.
  - `skills/`: Staged modular task instructions.
  - `principles/`: Staged global rules/constitutions.
- `src/axon/`: The Python CLI source code.

## Target Adapters
Different IDEs and Agents ingest context differently. Axon handles this using the `AgentAdapter` class defined in `adapters.py`.

### 1. Symlinking (Modular Instructions)
Agents like **Gemini / Antigravity**, **Devin**, **Codex**, and **Cursor** support modular `.md` files in designated folders (`.agents/skills/`, `.agents/rules/`, `.codex/skills/`, `.cursor/rules/`). 
Axon creates symbolic links from `~/.axon/skills/my-skill.md` directly into the target project's local folder. This ensures that any upstream edits to the skill/rule in `~/.axon/` are immediately reflected across all projects.

### 2. File Compilation (Single-File Targets)
Agents like **Claude Code** (`CLAUDE.md`), **Devin** (`AGENTS.md`), **Codex** (`AGENTS.md`), and **Cursor** (`.cursorrules`) use single-file targets for project constitution rules. 
While V1 of Axon focuses heavily on modular symlinking for skills and rules, the architecture supports compiling (concatenating) principles into single-file targets like `CLAUDE.md` and `AGENTS.md`. 

## State Management (`core.py`)
State is strictly managed in `~/.axon/config.yaml`.
The config is structured hierarchically:
```yaml
agents:
  cursor:
    local:
      skills: ["python-basics.md"]
    global:
      skills: []
  gemini:
    global:
      skills: ["python-basics.md"]
```
This allows `axon list` and `axon sync` to accurately reflect and repair the system state on a granular, per-agent level.
