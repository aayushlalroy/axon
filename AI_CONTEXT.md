# AI Context for Axon

**Hello fellow AI Agent!** If you are reading this, you are looking at the source code for the Axon CLI.
Axon is a tool used by humans to manage skills and rules for *us* (AI Agents).

## Important Constraints & Rules
1. **Never edit `~/.axon/config.yaml` manually via shell commands (e.g. `sed`).** Always use the Python CLI commands (`axon enable`, `axon disable`) to manage state, or call the helper functions in `src/axon/core.py`.
2. **Do not modify `.cursorrules` directly.** Axon uses a Target Adapter pattern (see `adapters.py`). If you need to add a new rule for an agent, stage it as a modular markdown file in `~/.axon/principles/` and use the CLI to enable it.
3. **Idempotency is Key.** If you are contributing Python code to `cli.py`, ensure that all operations are idempotent. Creating a symlink that already exists should gracefully no-op or clean up the old link.

## Code Navigation
- `pyproject.toml`: The entry point definition (`axon = axon.cli:cli`).
- `src/axon/cli.py`: The `click` CLI interface. All user-facing commands (`add`, `import`, `enable`, `disable`, `activate`, `deactivate`, `remove`, `sync`, `list`) live here.
- `src/axon/core.py`: File I/O for the `~/.axon/` global hub, name normalization, additional files handling, and ignore filters.
- `src/axon/adapters.py`: Definitions of supported agents (`Cursor`, `Claude`, `Gemini`, `Devin`, `Codex`, `Windsurf`, `Copilot`) and their respective file paths.
- `CONFIG.md`: Configuration schema and guide for `axon-config.yaml` and `axon-import.yaml`.

## Extending Axon
To add support for a new AI IDE (e.g. GitHub Copilot, Windsurf):
1. Open `src/axon/agents.yaml` or `src/axon/adapters.py`.
2. Add a new `AgentAdapter` entry to the `ADAPTERS` dictionary mapping the agent's expected file paths (local and global).
3. The CLI (`enable`/`disable`/`list`/`init`/`import`/`remove`) will automatically pick up the new adapter. No changes needed in `cli.py`!

## Community Resources & Blog Posts

* 📦 **[ai-assets Repository](https://github.com/aayushlalroy/ai-assets)** — Official community repository containing production-ready skills, principles, and workflows.
* 📦 **[Axon Repository](https://github.com/aayushlalroy/axon)** — Official source code and documentation for Axon CLI.
* ✍️ **[Axon CLI Blog Post](https://www.roya2yush.com/writing/axon-ai-agent-skill-management)** — Deep dive into Axon's skill and constitution management system.
* ✍️ **[AI Assets Blog Post](https://www.roya2yush.com/writing/ai-assets-production-ready-agent-skills)** — Guide to production-ready agent skills and principles.
* 🧠 **[Skills, Principles & Workflows Architecture](https://www.roya2yush.com/writing/ai-agent-skills-principles-workflows-architecture)** — Architectural guide explaining how skills, principles, and workflows operate together.
