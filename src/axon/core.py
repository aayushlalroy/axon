import os
import shutil
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


def get_target_file(item_path: Path) -> Path:
    """Return the markdown file containing frontmatter for a skill/principle."""
    if item_path.is_dir():
        skill_md = item_path / "SKILL.md"
        if skill_md.exists():
            return skill_md
        md_files = list(item_path.glob("*.md")) + list(item_path.glob("*.mdc"))
        if md_files:
            return md_files[0]
        return skill_md
    return item_path


def parse_frontmatter(file_path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter and body from a markdown file."""
    if not file_path.exists() or not file_path.is_file():
        return {}, ""
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    if not lines:
        return {}, ""
    
    if lines[0].strip() == "---":
        end_idx = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx != -1:
            fm_text = "".join(lines[1:end_idx])
            body_text = "".join(lines[end_idx + 1:])
            try:
                fm_dict = yaml.safe_load(fm_text) or {}
                if isinstance(fm_dict, dict):
                    return fm_dict, body_text
            except Exception:
                pass
    return {}, content


def update_frontmatter(file_path: Path, updates: dict):
    """Update YAML frontmatter of a markdown file while preserving body text."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fm, body = parse_frontmatter(file_path)
    fm.update(updates)
    fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False).strip()
    body_clean = body if body.startswith("\n") else ("\n" + body if body else "\n")
    new_content = f"---\n{fm_str}\n---{body_clean}"
    file_path.write_text(new_content, encoding="utf-8")


def get_auto_invocation_status(item_path: Path) -> bool:
    """Check if model auto-invocation is enabled for an item (returns True if enabled, False if disabled)."""
    target_file = get_target_file(item_path)
    if not target_file.exists():
        return True
    fm, _ = parse_frontmatter(target_file)
    dis1 = fm.get("disable-model-invocation")
    dis2 = fm.get("disable_model_invocation")
    val = dis1 if dis1 is not None else dis2
    if val is True or (isinstance(val, str) and val.lower() == "true"):
        return False
    return True


def set_auto_invocation(item_path: Path, enable_auto_invocation: bool):
    """Set model auto-invocation flag on an item."""
    target_file = get_target_file(item_path)
    fm, _ = parse_frontmatter(target_file)
    key = "disable_model_invocation" if "disable_model_invocation" in fm else "disable-model-invocation"
    disable_flag = not enable_auto_invocation
    update_frontmatter(target_file, {key: disable_flag})


def is_content_equal(path_a: Path, path_b: Path) -> bool:
    """Compare contents of two files/directories to check if they match."""
    if not path_a.exists() or not path_b.exists():
        return False
    
    real_a = path_a.resolve()
    real_b = path_b.resolve()
    if real_a == real_b:
        return True

    if real_a.is_file() and real_b.is_file():
        return real_a.read_bytes() == real_b.read_bytes()
        
    if real_a.is_dir() and real_b.is_dir():
        files_a = {p.relative_to(real_a) for p in real_a.glob("**/*") if p.is_file() and p.name != ".DS_Store"}
        files_b = {p.relative_to(real_b) for p in real_b.glob("**/*") if p.is_file() and p.name != ".DS_Store"}
        if files_a != files_b:
            return False
        for rel_p in files_a:
            if (real_a / rel_p).read_bytes() != (real_b / rel_p).read_bytes():
                return False
        return True
        
    return False


def ensure_local_target(src_path: Path, dest_path: Path, require_copy: bool = False):
    """Ensure dest_path is correctly set up as a symlink or physical copy override."""
    dest_dir = dest_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    if require_copy:
        if dest_path.is_symlink():
            dest_path.unlink()
            if src_path.is_dir():
                shutil.copytree(src_path, dest_path)
            else:
                shutil.copy2(src_path, dest_path)
        elif not dest_path.exists():
            if src_path.is_dir():
                shutil.copytree(src_path, dest_path)
            else:
                shutil.copy2(src_path, dest_path)
    else:
        if not dest_path.is_symlink():
            if dest_path.exists():
                if dest_path.is_dir():
                    shutil.rmtree(dest_path)
                else:
                    dest_path.unlink()
            os.symlink(src_path, dest_path)


