# Axon

**Axon** is a universal Skill & Constitution Management System for AI Agents.

Axon provides a unified CLI (`axon`) to manage, stage, and compile system prompts ("Principles") and modular task instructions ("Skills") across multiple AI agent environments like Cursor, Claude Code, and Gemini/Antigravity.

## Features

- **Global Central Storage**: All your skills and principles live in `~/.axon/`. You can access them from any project folder on your machine.
- **Target Adapters**: Axon automatically translates your modular files into the format expected by the specific agent you are using (e.g., compiling rules into `.cursorrules` vs symlinking them into `.agents/skills/`).
- **Interactive Staging**: Use `axon add` to safely preview and classify new skills before adopting them.
- **Granular Scoping**: Enable skills locally for a specific project repository, or globally across your entire system.

## Quick Start

### Installation

```bash
git clone https://github.com/aayushlalroy/axon.git
cd axon
pip install -e .
```

### Usage

1. **Initialize a Project**:
   ```bash
   cd your-project
   axon init
   ```
   This scaffolds the necessary directories (`.cursor/rules/`, `.agents/skills/`, etc.) in your project.

2. **Stage a Skill**:
   ```bash
   axon add path/to/my-skill.md
   ```
   Follow the interactive wizard to stage the skill globally in `~/.axon/skills/`.

3. **Enable a Skill**:
   ```bash
   # Enable locally (current project)
   axon enable skill my-skill.md
   
   # Enable globally (across all compatible agents)
   axon enable skill my-skill.md --global
   ```

4. **View Status**:
   ```bash
   axon list
   ```

## Commands Reference
- `axon init`
- `axon agents`
- `axon add <path>`
- `axon enable <type> <name> [--global | --local] [--agent <agent>]`
- `axon disable <type> <name> [--global | --local] [--agent <agent>]`
- `axon sync`
- `axon list [--all]`
