import os
from pathlib import Path
from rich.console import Console

console = Console()

class AgentAdapter:
    def __init__(self, name, local_paths, global_paths=None, supports_compile=False):
        self.name = name
        self.local_paths = local_paths
        self.global_paths = global_paths or []
        self.supports_compile = supports_compile

ADAPTERS = {
    "cursor": AgentAdapter(
        name="Cursor",
        local_paths=[Path(".cursor/rules"), Path(".cursorrules")],
        supports_compile=True
    ),
    "claude": AgentAdapter(
        name="Claude Code",
        local_paths=[Path(".clauderc")],
        supports_compile=True
    ),
    "gemini": AgentAdapter(
        name="Gemini/Antigravity",
        local_paths=[Path(".agents/skills"), Path(".agents/rules")],
        global_paths=[Path(os.path.expanduser("~/.gemini/config/skills")), Path(os.path.expanduser("~/.gemini/config/rules"))]
    )
}

def scaffold_local_env(agent_name):
    adapter = ADAPTERS.get(agent_name)
    if not adapter:
        return False
    
    for path in adapter.local_paths:
        if path.suffix: # it's a file
            if not path.exists():
                path.touch()
                console.print(f"[green]Created {path}[/green]")
        else: # it's a directory
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                console.print(f"[green]Created {path}/[/green]")
    return True
