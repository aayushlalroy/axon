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

### 1. Symlinking (Default)
Agents like **Antigravity (AGY)** and **Claude Code** support modular `.md` files in designated folders (`.agents/skills/`). 
Axon creates symbolic links from `~/.axon/skills/my-skill.md` directly into the project's local `.agents/skills/` folder. This ensures that any upstream edits to the skill in `~/.axon/` are immediately reflected across all projects.

### 2. File Compilation (Monoliths)
Agents like **Cursor** do not support a global file-based ruleset, and often rely on a single monolithic `.cursorrules` file.
While V1 of Axon focuses heavily on modular symlinking for `.cursor/rules/` (Cursor MDC), the architecture supports "compiling" (concatenating) principles into a single `.cursorrules` file. 

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
