import os
import shutil
import yaml
from pathlib import Path
from rich.console import Console

console = Console()
AXON_DIR = Path(os.path.expanduser("~/.axon"))
CONFIG_FILE = AXON_DIR / "config.yaml"


def get_config_file() -> Path:
    return AXON_DIR / "config.yaml"


def init_axon_dir():
    """Ensure ~/.axon directory structure exists."""
    AXON_DIR.mkdir(parents=True, exist_ok=True)
    (AXON_DIR / "skills").mkdir(exist_ok=True)
    (AXON_DIR / "principles").mkdir(exist_ok=True)
    (AXON_DIR / "workflows").mkdir(exist_ok=True)
    cfg_file = get_config_file()
    if not cfg_file.exists():
        with open(cfg_file, "w") as f:
            yaml.dump({"skills": {}, "principles": {}, "workflows": {}}, f)


def load_config():
    init_axon_dir()
    cfg_file = get_config_file()
    with open(cfg_file, "r") as f:
        return yaml.safe_load(f) or {"skills": {}, "principles": {}, "workflows": {}}


def save_config(config):
    cfg_file = get_config_file()
    with open(cfg_file, "w") as f:
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


def stage_skill(src: Path, dest_name: str, overwrite: bool = False, custom_ignores: list[str] = None) -> Path:
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
        # Copy folder contents into the staged folder, excluding ignored files
        for item in src.iterdir():
            if should_ignore_file(item, custom_ignores):
                continue
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


def normalize_name(name: str) -> str:
    """Strip .md, .mdc extensions to produce canonical base item name."""
    if not name:
        return ""
    clean = name.strip()
    if clean.endswith(".mdc"):
        return clean[:-4]
    if clean.endswith(".md"):
        return clean[:-3]
    return clean


DEFAULT_IGNORE_PATTERNS = ["README.md", "INDEX.md", ".DS_Store", "*.tmp", ".git*"]


def should_ignore_file(path: Path, custom_ignores: list[str] = None) -> bool:
    """Check if a file or path matches default or custom ignore patterns."""
    name = path.name
    patterns = list(DEFAULT_IGNORE_PATTERNS)
    
    # Load ignore_patterns from ~/.axon/config.yaml or local axon-config.yaml if present
    try:
        cfg = load_config()
        cfg_ignores = cfg.get("defaults", {}).get("ignore_patterns", [])
        if isinstance(cfg_ignores, list):
            for pat in cfg_ignores:
                if pat not in patterns:
                    patterns.append(pat)
    except Exception:
        pass

    if custom_ignores:
        for pat in custom_ignores:
            if pat not in patterns:
                patterns.append(pat)

    import fnmatch
    for pat in patterns:
        if fnmatch.fnmatch(name, pat) or name == pat:
            return True
    return False


def get_staged_types_for_item(name: str) -> list[str]:
    """Return all staged types ('skill', 'principle', 'workflow') for a clean item name."""
    clean = normalize_name(name)
    staged = get_staged_items()
    types = []

    if clean in staged["skills"]:
        types.append("skill")
    if f"{clean}.md" in staged["principles"] or clean in staged["principles"]:
        types.append("principle")
    if f"{clean}.md" in staged["workflows"] or clean in staged["workflows"]:
        types.append("workflow")

    return types


def get_skill_additional_files(skill_path: Path, custom_ignores: list[str] = None) -> list[Path]:
    """Return all auxiliary/additional files in a skill directory excluding SKILL.md and ignored files."""
    if not skill_path.exists() or not skill_path.is_dir():
        return []

    additional = []
    for file in skill_path.glob("**/*"):
        if file.is_file():
            rel = file.relative_to(skill_path)
            if rel.name == "SKILL.md":
                continue
            if should_ignore_file(file, custom_ignores) or should_ignore_file(rel, custom_ignores):
                continue
            additional.append(rel)

    return sorted(additional)


def add_additional_file_to_skill(skill_name: str, src_file: Path) -> Path:
    """Copy an additional file into an existing staged skill directory."""
    clean_skill = normalize_name(skill_name)
    skill_dir = AXON_DIR / "skills" / clean_skill
    if not skill_dir.exists() or not skill_dir.is_dir():
        raise FileNotFoundError(f"Staged skill '{clean_skill}' does not exist.")

    dest = skill_dir / src_file.name
    shutil.copy2(src_file, dest)
    return dest


def register_shared_additional_file(aux_rel_path: str, skill_name: str):
    """Record that skill_name is actively using auxiliary file aux_rel_path."""
    config = load_config()
    shared = config.get("shared_additional_files", {})
    if aux_rel_path not in shared:
        shared[aux_rel_path] = []
    if skill_name not in shared[aux_rel_path]:
        shared[aux_rel_path].append(skill_name)
    config["shared_additional_files"] = shared
    save_config(config)


def unregister_shared_additional_file(aux_rel_path: str, skill_name: str) -> bool:
    """Unregister skill_name from auxiliary file. Returns True if 0 active skills remain referencing it."""
    config = load_config()
    shared = config.get("shared_additional_files", {})
    if aux_rel_path in shared:
        if skill_name in shared[aux_rel_path]:
            shared[aux_rel_path].remove(skill_name)
        if not shared[aux_rel_path]:
            del shared[aux_rel_path]
            config["shared_additional_files"] = shared
            save_config(config)
            return True
    save_config(config)
    return aux_rel_path not in shared


def remove_staged_item(item_name: str, item_type: str = None) -> list[str]:
    """
    Remove staged item from ~/.axon hub and clean up agent targets & config.
    Returns list of removed types.
    """
    from axon.adapters import ADAPTERS
    clean_name = normalize_name(item_name)
    staged_types = get_staged_types_for_item(clean_name)

    target_types = [item_type] if item_type else staged_types
    removed = []

    config = load_config()

    for t in target_types:
        staged_path = None
        add_files = []
        if t == "skill":
            staged_path = AXON_DIR / "skills" / clean_name
            if staged_path.exists() and staged_path.is_dir():
                add_files = get_skill_additional_files(staged_path)
        elif t in ("principle", "workflow"):
            staged_path = AXON_DIR / f"{t}s" / f"{clean_name}.md"

        if staged_path and staged_path.exists():
            if staged_path.is_dir():
                shutil.rmtree(staged_path)
            else:
                staged_path.unlink()
            removed.append(t)

        # Cleanup agent symlinks & overrides across all adapters
        for ag, adapter in ADAPTERS.items():
            for scope in ("local", "global"):
                is_glob = (scope == "global")
                target_dirs = adapter.get_dir_paths(t, is_global=is_glob)
                dest_name = clean_name
                if t == "skill":
                    suffix = adapter.get_skill_suffix()
                    dest_name = f"{clean_name}{suffix}" if suffix else clean_name
                else:
                    dest_name = f"{clean_name}.md"

                for target_dir in target_dirs:
                    dest_path = target_dir / dest_name
                    if dest_path.is_symlink() or dest_path.is_file():
                        dest_path.unlink()
                    elif dest_path.is_dir():
                        shutil.rmtree(dest_path)

                    # Also remove auxiliary files linked into target_dir if skill
                    if t == "skill" and not adapter.uses_skill_folders:
                        for aux_file in add_files:
                            should_remove = unregister_shared_additional_file(str(aux_file), clean_name)
                            if should_remove:
                                aux_dest = target_dir / aux_file.name
                                if aux_dest.exists() or aux_dest.is_symlink():
                                    if aux_dest.is_symlink() or aux_dest.is_file():
                                        aux_dest.unlink()
                                    elif aux_dest.is_dir():
                                        shutil.rmtree(aux_dest)

                # Cleanup config entry
                update_config_state(ag, scope, f"{t}s", clean_name, enable=False)
                if t == "principle":
                    compile_principles_for_agent(ag, scope)

    return removed


def extract_name_from_source(src: Path, name_source: str = "auto") -> str:
    """
    Extract item name based on name_source strategy:
    - 'frontmatter': Extract name from YAML frontmatter in SKILL.md or .md file.
    - 'folder': Use folder name (if dir) or parent folder name.
    - 'file': Use file stem.
    - 'auto': Try frontmatter first, then folder (for dir) or file stem (for file).
    """
    if name_source == "auto":
        try:
            cfg = load_config()
            cfg_ns = cfg.get("defaults", {}).get("name_source") or cfg.get("import", {}).get("name_source")
            if cfg_ns and cfg_ns in ("frontmatter", "folder", "file"):
                name_source = cfg_ns
        except Exception:
            pass

    if name_source == "folder":
        return src.name if src.is_dir() else src.parent.name
    if name_source == "file":
        return src.stem

    # Strategy 'frontmatter' or 'auto'
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

    if name_source == "frontmatter":
        # Fallback to folder/file stem if frontmatter name missing
        return src.name if src.is_dir() else src.stem

    # Default 'auto' fallback
    return src.name if src.is_dir() else src.stem


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
        clean = normalize_name(p_name)
        p_path = AXON_DIR / "principles" / f"{clean}.md"

        if p_path.exists():
            content = p_path.read_text(encoding="utf-8").strip()
            blocks.append(f"## {clean}\n\n{content}")

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



