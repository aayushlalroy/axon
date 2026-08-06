import os
from pathlib import Path
from rich.console import Console

console = Console()

class AgentAdapter:
    def __init__(
        self,
        name,
        local_skill_paths=None,
        local_principle_paths=None,
        global_skill_paths=None,
        global_principle_paths=None,
        supports_compile=False,
    ):
        self.name = name
        self.local_skill_paths = local_skill_paths or []
        self.local_principle_paths = local_principle_paths or []
        self.global_skill_paths = global_skill_paths or []
        self.global_principle_paths = global_principle_paths or []
        self.supports_compile = supports_compile

    def get_paths(self, item_type: str, is_global: bool = False):
        """Return the target paths for a given item type ('skill' or 'principle')."""
        if item_type.startswith("skill"):
            return self.global_skill_paths if is_global else self.local_skill_paths
        else:
            return self.global_principle_paths if is_global else self.local_principle_paths

    @property
    def local_paths(self):
        """Combined list of all local paths for scaffolding/init."""
        return list(dict.fromkeys(self.local_skill_paths + self.local_principle_paths))

    @property
    def global_paths(self):
        """Combined list of all global paths."""
        return list(dict.fromkeys(self.global_skill_paths + self.global_principle_paths))

ADAPTERS = {
    "cursor": AgentAdapter(
        name="Cursor",
        local_skill_paths=[Path(".cursor/rules")],
        local_principle_paths=[Path(".cursor/rules"), Path(".cursorrules")],
        supports_compile=True
    ),
    "claude": AgentAdapter(
        name="Claude Code",
        local_skill_paths=[Path(".clauderc")],
        local_principle_paths=[Path(".clauderc")],
        supports_compile=True
    ),
    "gemini": AgentAdapter(
        name="Gemini/Antigravity",
        local_skill_paths=[Path(".agents/skills")],
        local_principle_paths=[Path(".agents/rules")],
        global_skill_paths=[Path(os.path.expanduser("~/.gemini/config/skills"))],
        global_principle_paths=[Path(os.path.expanduser("~/.gemini/config/rules"))]
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
