import os
import yaml
from pathlib import Path
from rich.console import Console

console = Console()
AXON_DIR = Path(os.path.expanduser("~/.axon"))
CONFIG_FILE = AXON_DIR / "config.yaml"


def init_axon_dir():
    """Ensure ~/.axon directory structure exists."""
    AXON_DIR.mkdir(parents=True, exist_ok=True)
    (AXON_DIR / "skills").mkdir(exist_ok=True)
    (AXON_DIR / "principles").mkdir(exist_ok=True)
    (AXON_DIR / "workflows").mkdir(exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w") as f:
            yaml.dump({"skills": {}, "principles": {}, "workflows": {}}, f)


def load_config():
    init_axon_dir()
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {"skills": {}, "principles": {}, "workflows": {}}


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def update_config_state(agent_name, scope, item_type, item_name, enable=True):
    """
    Record or remove an enabled item in config.yaml.
    item_type is one of: 'skills', 'principles', 'workflows'
    scope is 'local' or 'global'
    """
    config = load_config()
    if "agents" not in config:
        config["agents"] = {}
    if agent_name not in config["agents"]:
        config["agents"][agent_name] = {}
    if scope not in config["agents"][agent_name]:
        config["agents"][agent_name][scope] = {}

    if item_type not in config["agents"][agent_name][scope]:
        config["agents"][agent_name][scope][item_type] = []

    items = config["agents"][agent_name][scope][item_type]
    if enable:
        if item_name not in items:
            items.append(item_name)
    else:
        if item_name in items:
            items.remove(item_name)

    save_config(config)


def get_staged_items():
    """
    Return all items in the ~/.axon staging hub.
    Skills are ALWAYS stored as named folders containing SKILL.md
    (the AgentSkills open standard). Principles and workflows are flat files.
    """
    _skill_dir = AXON_DIR / "skills"
    _principle_dir = AXON_DIR / "principles"
    _workflow_dir = AXON_DIR / "workflows"

    skills = [
        f.name for f in _skill_dir.iterdir()
        if f.name != ".DS_Store" and f.is_dir()
    ] if _skill_dir.exists() else []

    principles = [
        f.name for f in _principle_dir.iterdir()
        if f.name != ".DS_Store" and f.is_file()
    ] if _principle_dir.exists() else []

    workflows = [
        f.name for f in _workflow_dir.iterdir()
        if f.name != ".DS_Store" and f.is_file()
    ] if _workflow_dir.exists() else []

    return {"skills": skills, "principles": principles, "workflows": workflows}


def stage_skill(src: Path, dest_name: str, overwrite: bool = False) -> Path:
    """
    Stage a skill into ~/.axon/skills/<dest_name>/.
    Skills in the staging hub ALWAYS use the folder/SKILL.md layout.
    - If src is already a folder containing SKILL.md → copy the folder as-is.
    - If src is a plain .md file → create a folder and place it as SKILL.md.
    Returns the path to the staged folder.
    """
    init_axon_dir()
    dest = AXON_DIR / "skills" / dest_name
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Skill '{dest_name}' already staged at {dest}")
    if dest.exists():
        import shutil
        shutil.rmtree(dest)

    dest.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        import shutil
        # Copy entire folder contents into the staged folder
        for item in src.iterdir():
            s = str(item)
            d = str(dest / item.name)
            if item.is_dir():
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
        # Ensure SKILL.md exists (may have been named differently)
        if not (dest / "SKILL.md").exists():
            # If the source had a single .md file, rename it to SKILL.md
            md_files = list(dest.glob("*.md"))
            if len(md_files) == 1:
                md_files[0].rename(dest / "SKILL.md")
    else:
        # Flat .md or .mdc file → wrap in SKILL.md
        import shutil
        shutil.copy2(src, dest / "SKILL.md")

    return dest


def stage_principle(src: Path, dest_name: str, overwrite: bool = False) -> Path:
    """
    Stage a principle (flat file) into ~/.axon/principles/<dest_name>.
    Returns the path to the staged file.
    """
    import shutil
    init_axon_dir()
    dest = AXON_DIR / "principles" / dest_name
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Principle '{dest_name}' already staged at {dest}")
    if src.is_dir():
        raise ValueError(f"Principles must be flat files, not directories: {src}")
    shutil.copy2(src, dest)
    return dest


def stage_workflow(src: Path, dest_name: str, overwrite: bool = False) -> Path:
    """
    Stage a workflow (flat .md file) into ~/.axon/workflows/<dest_name>.
    Returns the path to the staged file.
    """
    import shutil
    init_axon_dir()
    dest = AXON_DIR / "workflows" / dest_name
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Workflow '{dest_name}' already staged at {dest}")
    if src.is_dir():
        raise ValueError(f"Workflows must be flat files, not directories: {src}")
    shutil.copy2(src, dest)
    return dest


def extract_name_from_source(src: Path) -> str:
    """
    Extract item name from YAML frontmatter if present (e.g. `name: foo`),
    otherwise fall back to stem for files or folder name for directories.
    """
    target_file = None
    if src.is_dir():
        if (src / "SKILL.md").exists():
            target_file = src / "SKILL.md"
        else:
            md_files = list(src.glob("*.md"))
            if len(md_files) == 1:
                target_file = md_files[0]
    elif src.is_file():
        target_file = src

    if target_file and target_file.exists():
        try:
            content = target_file.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1])
                    if isinstance(fm, dict) and fm.get("name"):
                        return str(fm["name"]).strip()
        except Exception:
            pass

    return src.stem if src.is_file() else src.name


AXON_BEGIN_MARKER = "<!-- AXON:BEGIN -->"
AXON_END_MARKER = "<!-- AXON:END -->"


def compile_principles_for_agent(agent_name: str, scope: str = "local"):
    """
    Compile all enabled principles for an agent into its single-file targets
    (e.g., AGENTS.md, CLAUDE.md, .cursorrules, .windsurfrules, .github/copilot-instructions.md).
    Preserves user content outside AXON:BEGIN / AXON:END tags.
    """
    from axon.adapters import ADAPTERS

    if agent_name not in ADAPTERS:
        return

    adapter = ADAPTERS[agent_name]
    if not adapter.supports_compile:
        return

    is_global = (scope == "global")
    file_targets = adapter.global_file_targets if is_global else adapter.local_file_targets
    if not file_targets:
        return

    config = load_config()
    enabled_principles = (
        config.get("agents", {})
        .get(agent_name, {})
        .get(scope, {})
        .get("principles", [])
    )

    blocks = []
    for p_name in enabled_principles:
        p_path = AXON_DIR / "principles" / p_name
        if not p_path.exists() and not p_name.endswith(".md"):
            p_path = AXON_DIR / "principles" / f"{p_name}.md"

        if p_path.exists():
            content = p_path.read_text(encoding="utf-8").strip()
            title = p_name.rsplit(".", 1)[0]
            blocks.append(f"## {title}\n\n{content}")

    if blocks:
        compiled_section = (
            f"{AXON_BEGIN_MARKER}\n"
            f"# Principles (Managed by Axon)\n\n"
            + "\n\n".join(blocks)
            + f"\n{AXON_END_MARKER}"
        )
    else:
        compiled_section = ""

    for target_file in file_targets:
        _update_target_file_with_compiled_section(target_file, compiled_section)


def _update_target_file_with_compiled_section(target_file: Path, compiled_section: str):
    if not target_file.parent.exists():
        target_file.parent.mkdir(parents=True, exist_ok=True)

    existing_text = target_file.read_text(encoding="utf-8") if target_file.exists() else ""

    if AXON_BEGIN_MARKER in existing_text and AXON_END_MARKER in existing_text:
        before = existing_text.split(AXON_BEGIN_MARKER)[0].rstrip()
        after = existing_text.split(AXON_END_MARKER)[1].lstrip()

        if compiled_section:
            new_text = (before + "\n\n" + compiled_section + "\n\n" + after).strip() + "\n"
        else:
            new_text = (before + "\n\n" + after).strip()
            if new_text:
                new_text += "\n"
    else:
        if compiled_section:
            if existing_text.strip():
                new_text = existing_text.rstrip() + "\n\n" + compiled_section + "\n"
            else:
                new_text = compiled_section + "\n"
        else:
            new_text = existing_text

    target_file.write_text(new_text, encoding="utf-8")

