import os
import shutil
from pathlib import Path
from rich.console import Console

console = Console()

class AgentAdapter:
    def __init__(
        self,
        name,
        local_skill_dirs=None,
        local_principle_dirs=None,
        global_skill_dirs=None,
        global_principle_dirs=None,
        local_file_targets=None,
        global_file_targets=None,
        supports_compile=False,
    ):
        self.name = name
        self.local_skill_dirs = local_skill_dirs or []
        self.local_principle_dirs = local_principle_dirs or []
        self.global_skill_dirs = global_skill_dirs or []
        self.global_principle_dirs = global_principle_dirs or []
        self.local_file_targets = local_file_targets or []
        self.global_file_targets = global_file_targets or []
        self.supports_compile = supports_compile

    def get_dir_paths(self, item_type: str, is_global: bool = False):
        """Return directory target paths where modular symlinks are placed."""
        if item_type.startswith("skill"):
            return self.global_skill_dirs if is_global else self.local_skill_dirs
        else:
            return self.global_principle_dirs if is_global else self.local_principle_dirs

    def get_opposite_dir_paths(self, item_type: str, is_global: bool = False):
        """Return directory target paths of the opposite item type (for stale symlink cleanup)."""
        if item_type.startswith("skill"):
            return self.global_principle_dirs if is_global else self.local_principle_dirs
        else:
            return self.global_skill_dirs if is_global else self.local_skill_dirs

    @property
    def all_local_dirs(self):
        return list(dict.fromkeys(self.local_skill_dirs + self.local_principle_dirs))

    @property
    def all_local_files(self):
        return list(dict.fromkeys(self.local_file_targets))

ADAPTERS = {
    "cursor": AgentAdapter(
        name="Cursor",
        local_skill_dirs=[Path(".cursor/rules")],
        local_principle_dirs=[Path(".cursor/rules")],
        local_file_targets=[Path(".cursorrules")],
        supports_compile=True
    ),
    "claude": AgentAdapter(
        name="Claude Code",
        local_file_targets=[Path(".clauderc")],
        supports_compile=True
    ),
    "gemini": AgentAdapter(
        name="Gemini/Antigravity",
        local_skill_dirs=[Path(".agents/skills")],
        local_principle_dirs=[Path(".agents/rules")],
        global_skill_dirs=[Path(os.path.expanduser("~/.gemini/config/skills"))],
        global_principle_dirs=[Path(os.path.expanduser("~/.gemini/config/rules"))]
    )
}

def scaffold_local_env(agent_name):
    adapter = ADAPTERS.get(agent_name)
    if not adapter:
        return False
    
    for path in adapter.all_local_dirs:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]Created directory {path}/[/green]")
            
    for path in adapter.all_local_files:
        if path.is_dir():
            shutil.rmtree(path)
        if not path.exists():
            path.touch()
            console.print(f"[green]Created file {path}[/green]")
            
    return True
