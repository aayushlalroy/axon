import os
import shutil
import yaml
from pathlib import Path
from rich.console import Console

console = Console()

# Skill format constants
SKILL_FORMAT_FOLDER = "folder_skill_md"   # <dir>/<name>/SKILL.md  (Devin, Claude, Gemini, Codex)
SKILL_FORMAT_FLAT_MDC = "flat_mdc"        # <dir>/<name>.mdc       (Cursor)
SKILL_FORMAT_FLAT_MD = "flat_md"          # <dir>/<name>.md        (Windsurf)
SKILL_FORMAT_NONE = "none"                # no skill files         (Copilot)


class AgentAdapter:
    def __init__(
        self,
        name,
        skill_format=SKILL_FORMAT_FOLDER,
        local_skill_dirs=None,
        local_principle_dirs=None,
        local_workflow_dirs=None,
        global_skill_dirs=None,
        global_principle_dirs=None,
        global_workflow_dirs=None,
        local_file_targets=None,
        global_file_targets=None,
        supports_compile=False,
    ):
        self.name = name
        self.skill_format = skill_format
        self.local_skill_dirs = local_skill_dirs or []
        self.local_principle_dirs = local_principle_dirs or []
        self.local_workflow_dirs = local_workflow_dirs or []
        self.global_skill_dirs = global_skill_dirs or []
        self.global_principle_dirs = global_principle_dirs or []
        self.global_workflow_dirs = global_workflow_dirs or []
        self.local_file_targets = local_file_targets or []
        self.global_file_targets = global_file_targets or []
        self.supports_compile = supports_compile

    @property
    def uses_skill_folders(self) -> bool:
        """True when skills must be stored as <name>/SKILL.md subfolders."""
        return self.skill_format == SKILL_FORMAT_FOLDER

    @property
    def supports_skills(self) -> bool:
        """True when this agent has any concept of discrete skill files."""
        return self.skill_format != SKILL_FORMAT_NONE

    def get_skill_suffix(self) -> str:
        """Return the file extension for flat-file skill formats, or '' for folder format."""
        if self.skill_format == SKILL_FORMAT_FLAT_MDC:
            return ".mdc"
        if self.skill_format == SKILL_FORMAT_FLAT_MD:
            return ".md"
        return ""  # folder format or none

    def get_dir_paths(self, item_type: str, is_global: bool = False):
        """Return directory target paths where modular symlinks are placed."""
        t = item_type.rstrip("s").lower()  # normalise 'skills' -> 'skill'
        if t == "skill":
            return self.global_skill_dirs if is_global else self.local_skill_dirs
        elif t == "workflow":
            return self.global_workflow_dirs if is_global else self.local_workflow_dirs
        else:  # principle
            return self.global_principle_dirs if is_global else self.local_principle_dirs

    def get_opposite_dir_paths(self, item_type: str, is_global: bool = False):
        """Return directory target paths of the OPPOSITE item type (stale symlink cleanup)."""
        t = item_type.rstrip("s").lower()
        current_dirs = self.get_dir_paths(t, is_global=is_global)
        if t == "skill":
            opp_dirs = self.global_principle_dirs if is_global else self.local_principle_dirs
        else:  # principle / workflow
            opp_dirs = self.global_skill_dirs if is_global else self.local_skill_dirs
        return [d for d in opp_dirs if d not in current_dirs]

    @property
    def all_local_dirs(self):
        all_dirs = (
            self.local_skill_dirs
            + self.local_principle_dirs
            + self.local_workflow_dirs
        )
        return list(dict.fromkeys(all_dirs))

    @property
    def all_local_files(self):
        return list(dict.fromkeys(self.local_file_targets))


def _to_paths(path_list):
    return [Path(os.path.expanduser(p)) for p in (path_list or [])]


def load_adapters_config():
    config_path = Path(__file__).parent / "agents.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, "r") as f:
        data = yaml.safe_load(f) or {}

    adapters = {}
    for key, info in data.items():
        local_cfg = info.get("local", {})
        global_cfg = info.get("global", {})
        adapters[key] = AgentAdapter(
            name=info.get("name", key.capitalize()),
            skill_format=info.get("skill_format", SKILL_FORMAT_FOLDER),
            local_skill_dirs=_to_paths(local_cfg.get("skills")),
            local_principle_dirs=_to_paths(local_cfg.get("principles")),
            local_workflow_dirs=_to_paths(local_cfg.get("workflows")),
            local_file_targets=_to_paths(local_cfg.get("files")),
            global_skill_dirs=_to_paths(global_cfg.get("skills")),
            global_principle_dirs=_to_paths(global_cfg.get("principles")),
            global_workflow_dirs=_to_paths(global_cfg.get("workflows")),
            global_file_targets=_to_paths(global_cfg.get("files")),
            supports_compile=info.get("supports_compile", False),
        )
    return adapters


ADAPTERS = load_adapters_config()


def get_initialized_project_agents(project_dir: Path = None, adapters_dict: dict = None) -> list:
    """
    Return list of agent keys that are initialized/managed in the project directory.
    An agent is initialized if any of its local directories or files physically exist.
    """
    if project_dir is None:
        project_dir = Path.cwd()
    if adapters_dict is None:
        adapters_dict = ADAPTERS
    initialized = []
    for key, adapter in adapters_dict.items():
        is_init = False
        all_dirs = getattr(adapter, "all_local_dirs", [])
        for p in all_dirs:
            check_path = p if p.is_absolute() else project_dir / p
            if check_path.exists():
                is_init = True
                break
        if not is_init:
            all_files = getattr(adapter, "all_local_files", [])
            for f in all_files:
                check_path = f if f.is_absolute() else project_dir / f
                if check_path.exists():
                    is_init = True
                    break
        if is_init:
            initialized.append(key)
    return initialized




def scaffold_local_env(agent_name: str) -> bool:
    adapter = ADAPTERS.get(agent_name)
    if not adapter:
        return False

    already_initialized = True
    for path in adapter.all_local_dirs:
        if not path.exists():
            already_initialized = False
            path.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]Created directory {path}/[/green]")

    for path in adapter.all_local_files:
        if path.is_dir():
            shutil.rmtree(path)
        if not path.exists():
            already_initialized = False
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            console.print(f"[green]Created file {path}[/green]")

    if already_initialized:
        console.print(f"[dim]Agent '{agent_name}' directories already present, skipping.[/dim]")

    return True

