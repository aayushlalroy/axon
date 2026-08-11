import click
import shutil
import subprocess
import sys
import os
import yaml
from importlib.metadata import version as pkg_version, PackageNotFoundError
from rich.console import Console
from rich.table import Table
from pathlib import Path
from axon import __version__
from axon.adapters import (
    ADAPTERS,
    scaffold_local_env,
    SKILL_FORMAT_FOLDER,
    SKILL_FORMAT_FLAT_MDC,
    SKILL_FORMAT_FLAT_MD,
    SKILL_FORMAT_NONE,
)
import axon.core
from axon.core import (
    get_staged_items,
    load_config,
    AXON_DIR,
    update_config_state,
    init_axon_dir,
    stage_skill,
    stage_principle,
    stage_workflow,
    extract_name_from_source,
    compile_principles_for_agent,
    set_auto_invocation,
    get_auto_invocation_status,
    ensure_local_target,
    is_content_equal,
    normalize_name,
    should_ignore_file,
    get_staged_types_for_item,
    get_skill_additional_files,
    add_additional_file_to_skill,
    register_shared_additional_file,
    unregister_shared_additional_file,
    remove_staged_item,
)

console = Console()

_PACKAGE_NAME = "axon-cli"
_REPO_URL = "https://github.com/aayushlalroy/axon.git"


def _get_installed_version() -> str:
    try:
        return pkg_version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return "unknown"


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _resolve_item_type(arg_list):
    """
    Parse positional args to detect an explicit item_type prefix or names only.
    Accepted prefixes: skill, skills, principle, principles, workflow, workflows
    Returns (item_type_or_None, [names])
    """
    if not arg_list:
        return None, []
    first = arg_list[0].lower()
    if first in ("skill", "skills"):
        return "skill", list(arg_list[1:])
    if first in ("principle", "principles"):
        return "principle", list(arg_list[1:])
    if first in ("workflow", "workflows"):
        return "workflow", list(arg_list[1:])
    return None, list(arg_list)


def _resolve_agents_to_target(agent_option):
    if not agent_option:
        return list(ADAPTERS.keys())
    agents_to_target = []
    items = agent_option if isinstance(agent_option, (tuple, list)) else [agent_option]
    for item in items:
        for part in item.split(","):
            part = part.strip()
            if not part:
                continue
            matched_key = None
            for key in ADAPTERS.keys():
                if key.lower() == part.lower():
                    matched_key = key
                    break
            target_key = matched_key if matched_key else part
            if target_key not in agents_to_target:
                agents_to_target.append(target_key)
    return agents_to_target


def _resolve_scope(is_global_flag: bool) -> bool:
    if is_global_flag:
        return True
    try:
        cfg = load_config()
        if cfg.get("defaults", {}).get("scope") == "global":
            return True
    except Exception:
        pass
    return False


def _dest_name_for(name: str, adapter, item_type: str) -> str:
    """
    Compute the filename that should appear inside the agent's target directory.
    - skills with folder format: the folder name (no extension) → `name`
    - skills with flat_mdc: `name.mdc`
    - skills with flat_md or principle/workflow: `name.md` if name has no ext, else as-is
    """
    if item_type == "skill":
        suffix = adapter.get_skill_suffix()
        if not suffix:
            return name  # folder format
        return name if name.endswith(suffix) else f"{name}{suffix}"
    else:
        return name if name.endswith(".md") else f"{name}.md"


def _detect_staged_item_type(name: str, staged: dict, explicit_type: str = None):
    """
    Determine item_type and actual staged name for input `name`.
    Supports multi-type disambiguation prompts if an item is staged as multiple types.
    """
    has_md_ext = name.endswith(".md")
    clean_name = normalize_name(name)
    staged_types = get_staged_types_for_item(clean_name)

    if explicit_type:
        if explicit_type in staged_types:
            staged_name = f"{clean_name}.md" if explicit_type in ("principle", "workflow") else clean_name
            return explicit_type, staged_name
        else:
            other_types = [t for t in staged_types if t != explicit_type]
            if other_types:
                console.print(f"[yellow]Warning: '{name}' is staged as a {', '.join(other_types)}, not a {explicit_type}. Skipping.[/yellow]")
            else:
                console.print(f"[red]Error: '{name}' is not staged. Use 'axon add' first.[/red]")
            return None, clean_name

    if not staged_types:
        console.print(f"[red]Error: '{name}' is not staged. Use 'axon add' first.[/red]")
        return None, clean_name

    if has_md_ext:
        if "principle" in staged_types:
            return "principle", f"{clean_name}.md"
        if "workflow" in staged_types:
            return "workflow", f"{clean_name}.md"

    if len(staged_types) == 1:
        t = staged_types[0]
        staged_name = f"{clean_name}.md" if t in ("principle", "workflow") else clean_name
        return t, staged_name

    # Ambiguous - multiple staged types found!
    console.print(f"[yellow]'{clean_name}' is staged as multiple types:[/yellow]")
    options = staged_types + ["all"]
    for idx, opt in enumerate(options, 1):
        console.print(f"  {idx}) {opt}")
    choice = click.prompt("Select type to target", type=int, default=1)
    chosen_opt = options[choice - 1]
    if chosen_opt == "all":
        return "all", clean_name
    staged_name = f"{clean_name}.md" if chosen_opt in ("principle", "workflow") else clean_name
    return chosen_opt, staged_name


def _do_enable_item(
    src_path: Path,
    target_dir: Path,
    dest_name: str,
    adapter,
    item_type: str,
) -> bool:
    """
    Copy/sync the staged item into target_dir.
    For folder_skill_md agents: copy the whole skill folder.
    For flat file agents: link SKILL.md and additional auxiliary files.
    Returns True on success.
    """
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)

    clean_name = normalize_name(dest_name)
    dest_path = target_dir / dest_name

    if dest_path.is_symlink() or dest_path.is_file():
        dest_path.unlink()
    elif dest_path.is_dir():
        shutil.rmtree(dest_path)

    if item_type == "skill" and adapter.uses_skill_folders:
        if not src_path.is_dir():
            console.print(f"[red]Error: Staged skill '{src_path.name}' is not a folder. Re-stage it with 'axon add'.[/red]")
            return False
        os.symlink(src_path, dest_path)
    elif item_type == "skill" and adapter.skill_format in (SKILL_FORMAT_FLAT_MDC, SKILL_FORMAT_FLAT_MD):
        skill_md = src_path / "SKILL.md"
        if not skill_md.exists():
            console.print(f"[red]Error: No SKILL.md found inside staged skill '{src_path.name}'.[/red]")
            return False
        os.symlink(skill_md, dest_path)

        # Link additional/auxiliary files into target_dir for flat file agents
        add_files = get_skill_additional_files(src_path)
        for rel_file in add_files:
            aux_src = src_path / rel_file
            aux_dest = target_dir / rel_file.name
            if aux_dest.is_symlink() or aux_dest.is_file():
                aux_dest.unlink()
            os.symlink(aux_src, aux_dest)
            register_shared_additional_file(str(rel_file), clean_name)
    else:
        if src_path.is_dir():
            console.print(f"[red]Error: Staged {item_type} '{src_path.name}' is a folder, but {item_type}s must be flat files.[/red]")
            return False
        os.symlink(src_path, dest_path)

    return True


def _do_disable_item(target_dir: Path, dest_name: str, item_type: str = "skill", src_path: Path = None) -> bool:
    """Remove a copied file/folder/symlink from target_dir. Returns True if something was removed."""
    clean_name = normalize_name(dest_name)
    dest_path = target_dir / dest_name
    removed_any = False
    if dest_path.is_symlink() or dest_path.is_file():
        dest_path.unlink()
        removed_any = True
    elif dest_path.is_dir():
        shutil.rmtree(dest_path)
        removed_any = True

    if item_type == "skill" and src_path and src_path.exists() and src_path.is_dir():
        add_files = get_skill_additional_files(src_path)
        for rel_file in add_files:
            should_remove = unregister_shared_additional_file(str(rel_file), clean_name)
            if should_remove:
                aux_dest = target_dir / rel_file.name
                if aux_dest.exists() or aux_dest.is_symlink():
                    if aux_dest.is_symlink() or aux_dest.is_file():
                        aux_dest.unlink()
                    elif aux_dest.is_dir():
                        shutil.rmtree(aux_dest)

    return removed_any


# ─────────────────────────────────────────────────────────
# CLI commands
# ─────────────────────────────────────────────────────────

@click.group()
@click.version_option(__version__, "--version", "-v")
def cli():
    """Axon: Skill & Constitution Management System for AI Agents"""
    pass


@cli.command()
def agents():
    """List all currently supported agent adapters."""
    console.print("[bold green]Supported Agent Adapters:[/bold green]")
    for key, adapter in ADAPTERS.items():
        sf = adapter.skill_format
        skill_note = {
            SKILL_FORMAT_FOLDER: "folder/SKILL.md",
            SKILL_FORMAT_FLAT_MDC: ".mdc flat file",
            SKILL_FORMAT_FLAT_MD: ".md flat file",
            SKILL_FORMAT_NONE: "no skills",
        }.get(sf, sf)
        has_workflows = bool(adapter.local_workflow_dirs)
        wf_note = "✓ workflows" if has_workflows else "no workflows"
        console.print(f"  [bold]{key}[/bold] ({adapter.name}) — skills: {skill_note}, {wf_note}")


@cli.command()
def version():
    """Show the installed Axon CLI version."""
    v = _get_installed_version()
    console.print(f"[bold]axon[/bold] version [green]{v}[/green]")


@cli.command()
@click.option(
    "--version", "pin_version",
    default=None,
    help="Install a specific release tag or branch (e.g. v0.2.0). Defaults to latest.",
)
def update(pin_version):
    """Update Axon CLI to the latest (or a specific) version."""
    current = _get_installed_version()
    console.print(f"Current version: [bold]{current}[/bold]")

    if pin_version:
        target = f"git+{_REPO_URL}@{pin_version}"
        console.print(f"Updating to [bold]{pin_version}[/bold]…")
    else:
        target = f"git+{_REPO_URL}"
        console.print("Updating to [bold]latest[/bold]…")

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", target],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]Update failed.[/red] pip exited with code {exc.returncode}.")
        return

    new_version = _get_installed_version()
    if new_version != current:
        console.print(f"[bold green]✓ Updated:[/bold green] {current} → {new_version}")
    else:
        console.print(f"[bold green]✓ Already up to date:[/bold green] {new_version}")


@cli.command()
@click.option("--agent", multiple=True, help="Specify agents to initialize")
def init(agent):
    """Initialize current project folder for agents (creates target directories/files)."""
    agents_to_init = agent if agent else ADAPTERS.keys()
    for ag in agents_to_init:
        if ag not in ADAPTERS:
            console.print(f"[yellow]Warning: Agent '{ag}' is not supported.[/yellow]")
            continue
        console.print(f"Initializing {ADAPTERS[ag].name}…")
        scaffold_local_env(ag)
    console.print("[bold green]Initialization complete.[/bold green]")


def _is_item_present(adapter, item_type: str, name: str, is_global: bool):
    """Check if an item is physically present in the target paths for this agent/scope."""
    target_dirs = adapter.get_dir_paths(item_type, is_global=is_global)
    dest_name = _dest_name_for(name, adapter, item_type)

    for target_dir in target_dirs:
        dest_path = target_dir / dest_name
        if dest_path.exists() or dest_path.is_symlink():
            return True, dest_path

    if item_type == "principle" and adapter.supports_compile:
        file_targets = adapter.global_file_targets if is_global else adapter.local_file_targets
        for target_file in file_targets:
            if target_file.exists():
                text = target_file.read_text(encoding="utf-8", errors="ignore")
                clean = normalize_name(name)
                if clean in text or name in text:
                    return True, target_file

    return False, None


@cli.command(name="list")
@click.option("--all", "show_all", is_flag=True, help="List all available staged items.")
@click.option("--agent", help="Filter by specific agent")
def list_items(show_all, agent):
    """List skills/principles/workflows (enabled or all)."""
    staged = get_staged_items()

    if show_all:
        console.print("[bold cyan]All Staged Items in ~/.axon:[/bold cyan]")
        console.print("[bold]Skills:[/bold]")
        for s in staged["skills"]:
            skill_dir = axon.core.AXON_DIR / "skills" / s
            add_files = get_skill_additional_files(skill_dir)
            aux_str = f" [dim][additional files: {', '.join([f.name for f in add_files])}][/dim]" if add_files else ""
            console.print(f"  - {s}{aux_str}")

        console.print("\n[bold]Principles:[/bold]")
        for p in staged["principles"]:
            console.print(f"  - {p}")

        console.print("\n[bold]Workflows:[/bold]")
        for w in staged["workflows"]:
            console.print(f"  - {w}")
        return

    config = load_config()
    console.print("[bold cyan]Currently Enabled Items:[/bold cyan]")
    agents_to_list = _resolve_agents_to_target([agent] if agent else None)

    for ag in agents_to_list:
        if ag not in ADAPTERS:
            continue
        adapter = ADAPTERS[ag]
        console.print(f"\n[bold underline]{adapter.name}[/bold underline]")
        agent_config = config.get("agents", {}).get(ag, {})
        printed_any = False

        for scope_label in ("local", "global"):
            is_glob = (scope_label == "global")
            scope_cfg = agent_config.get(scope_label, {})
            skills = scope_cfg.get("skills", [])
            principles = scope_cfg.get("principles", [])
            workflows = scope_cfg.get("workflows", [])

            active_skills = []
            for s in skills:
                ok, path = _is_item_present(adapter, "skill", s, is_glob)
                if ok:
                    auto = get_auto_invocation_status(path) if path else True
                    auto_str = f"[dim][auto: {'on' if auto else 'off'}][/dim]"
                    stor_str = "[dim][symlink][/dim]" if path and path.is_symlink() else "[dim][override][/dim]"
                    active_skills.append(f"{s} {auto_str} {stor_str}")

            active_principles = []
            for p in principles:
                ok, path = _is_item_present(adapter, "principle", p, is_glob)
                if ok:
                    stor_str = "[dim][symlink][/dim]" if path and path.is_symlink() else ""
                    active_principles.append(f"{p}{(' ' + stor_str) if stor_str else ''}")

            active_workflows = []
            for w in workflows:
                ok, path = _is_item_present(adapter, "workflow", w, is_glob)
                if ok:
                    stor_str = "[dim][symlink][/dim]" if path and path.is_symlink() else ""
                    active_workflows.append(f"{w}{(' ' + stor_str) if stor_str else ''}")

            if not active_skills and not active_principles and not active_workflows:
                continue

            printed_any = True
            console.print(f"  [bold]{scope_label.capitalize()}:[/bold]")
            if active_skills:
                console.print("    [bold]Skills:[/bold]")
                for item in active_skills:
                    console.print(f"      - {item}")
            if active_principles:
                console.print("    [bold]Principles:[/bold]")
                for item in active_principles:
                    console.print(f"      - {item}")
            if active_workflows:
                console.print("    [bold]Workflows:[/bold]")
                for item in active_workflows:
                    console.print(f"      - {item}")

        if not printed_any:
            console.print("  [dim]No items enabled.[/dim]")


@cli.command()
@click.argument("source_path", type=click.Path(exists=True))
@click.option("--name", help="Override the default staged name")
@click.option(
    "--type", "item_types",
    multiple=True,
    help="Item type(s): skill, principle, workflow",
)
@click.option("--skill", "into_skill", help="Append file as an additional file to an existing staged skill")
def add(source_path, name, item_types, into_skill):
    """Stage a skill, principle, or workflow into the ~/.axon hub."""
    init_axon_dir()
    src = Path(source_path)

    # Handle appending additional file to an existing skill
    if into_skill:
        clean_skill = normalize_name(into_skill)
        try:
            dest = add_additional_file_to_skill(clean_skill, src)
            console.print(f"[bold green]Appended '{src.name}' as additional file into skill '{clean_skill}' → {dest}[/bold green]")
        except FileNotFoundError as exc:
            console.print(f"[red]Error: {exc}[/red]")
        return

    item_name = name if name else extract_name_from_source(src)
    clean_name = normalize_name(item_name)

    selected_types = list(item_types) if item_types else []

    if not selected_types:
        console.print(f"[bold cyan]Select type(s) to stage '{clean_name}' as:[/bold cyan]")
        console.print("  1) skill\n  2) principle\n  3) workflow\n  4) skill & principle\n  5) all")
        choice = click.prompt("Select option", type=int, default=1)
        if choice == 1:
            selected_types = ["skill"]
        elif choice == 2:
            selected_types = ["principle"]
        elif choice == 3:
            selected_types = ["workflow"]
        elif choice == 4:
            selected_types = ["skill", "principle"]
        else:
            selected_types = ["skill", "principle", "workflow"]

    for t in selected_types:
        try:
            if t == "skill":
                dest = stage_skill(src, clean_name, overwrite=True)
                add_files = get_skill_additional_files(dest)
                aux_note = f" (with additional files: {', '.join([f.name for f in add_files])})" if add_files else ""
                console.print(f"[bold green]Staged '{clean_name}' (skill){aux_note} → {dest}[/bold green]")
            elif t == "principle":
                dest = stage_principle(src, f"{clean_name}.md", overwrite=True)
                console.print(f"[bold green]Staged '{clean_name}' (principle) → {dest}[/bold green]")
            elif t == "workflow":
                dest = stage_workflow(src, f"{clean_name}.md", overwrite=True)
                console.print(f"[bold green]Staged '{clean_name}' (workflow) → {dest}[/bold green]")
        except Exception as e:
            console.print(f"[red]Error staging {t}: {e}[/red]")

    console.print("[dim]Use 'axon enable' to activate for an agent.[/dim]")


@cli.command(name="import")
@click.argument("import_path", type=click.Path(exists=True), default=".")
@click.option("--config", "config_file", type=click.Path(exists=True), help="Path to import configuration YAML")
@click.option("--name-source", "-n", type=click.Choice(["auto", "frontmatter", "folder", "file"]), default="auto", help="Strategy for item name extraction")
@click.option("--ignore", "-i", multiple=True, help="Additional glob pattern(s) to ignore")
@click.option("--dry-run", is_flag=True, help="Preview import without staging items")
def import_cmd(import_path, config_file, name_source, ignore, dry_run):
    """Bulk stage skills, principles, and workflows into ~/.axon hub."""
    init_axon_dir()
    base_dir = Path(import_path).resolve()
    custom_ignores = list(ignore)

    skills_to_import = []
    principles_to_import = []
    workflows_to_import = []

    # Check for config manifest
    manifest_path = Path(config_file) if config_file else None
    if not manifest_path:
        for cand in [base_dir / "axon-import.yaml", base_dir / "axon.yaml"]:
            if cand.exists():
                manifest_path = cand
                break

    if manifest_path and manifest_path.exists():
        console.print(f"[cyan]Using import manifest: {manifest_path}[/cyan]")
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            if manifest.get("name_source"):
                name_source = manifest["name_source"]
            if manifest.get("ignore"):
                custom_ignores.extend(manifest["ignore"])

            for item in manifest.get("skills", []):
                p = base_dir / item["path"] if not Path(item["path"]).is_absolute() else Path(item["path"])
                custom_name = item.get("name")
                skills_to_import.append((p, custom_name))

            for item in manifest.get("principles", []):
                p = base_dir / item["path"] if not Path(item["path"]).is_absolute() else Path(item["path"])
                custom_name = item.get("name")
                principles_to_import.append((p, custom_name))

            for item in manifest.get("workflows", []):
                p = base_dir / item["path"] if not Path(item["path"]).is_absolute() else Path(item["path"])
                custom_name = item.get("name")
                workflows_to_import.append((p, custom_name))
        except Exception as e:
            console.print(f"[red]Error parsing manifest {manifest_path}: {e}[/red]")
            return
    else:
        # Directory auto-scan
        skills_dir = base_dir / "skills"
        principles_dir = base_dir / "principles"
        workflows_dir = base_dir / "workflows"

        if skills_dir.exists() and skills_dir.is_dir():
            for child in skills_dir.iterdir():
                if not should_ignore_file(child, custom_ignores):
                    skills_to_import.append((child, None))

        if principles_dir.exists() and principles_dir.is_dir():
            for child in principles_dir.iterdir():
                if not should_ignore_file(child, custom_ignores):
                    principles_to_import.append((child, None))

        if workflows_dir.exists() and workflows_dir.is_dir():
            for child in workflows_dir.iterdir():
                if not should_ignore_file(child, custom_ignores):
                    workflows_to_import.append((child, None))

    staged = get_staged_items()
    results_table = Table(title="Axon Import Summary")
    results_table.add_column("Item Name", style="bold")
    results_table.add_column("Type", style="cyan")
    results_table.add_column("Additional Files", style="magenta")
    results_table.add_column("Status", style="green")

    staged_count = 0
    skipped_count = 0

    # Process Skills
    for src, override_name in skills_to_import:
        if not src.exists():
            continue
        item_name = override_name if override_name else extract_name_from_source(src, name_source)
        clean_name = normalize_name(item_name)

        if clean_name in staged["skills"]:
            results_table.add_row(clean_name, "skill", "-", "[dim]Skipped (Already Staged)[/dim]")
            skipped_count += 1
            continue

        add_files = get_skill_additional_files(src, custom_ignores) if src.is_dir() else []
        aux_str = ", ".join([f.name for f in add_files]) if add_files else "-"

        if not dry_run:
            try:
                stage_skill(src, clean_name, overwrite=False, custom_ignores=custom_ignores)
                results_table.add_row(clean_name, "skill", aux_str, "[green]Staged[/green]")
                staged_count += 1
            except Exception as exc:
                results_table.add_row(clean_name, "skill", aux_str, f"[red]Failed ({exc})[/red]")
        else:
            results_table.add_row(clean_name, "skill", aux_str, "[yellow]Would Stage (Dry Run)[/yellow]")

    # Process Principles
    for src, override_name in principles_to_import:
        if not src.exists():
            continue
        item_name = override_name if override_name else extract_name_from_source(src, name_source)
        clean_name = normalize_name(item_name)

        if f"{clean_name}.md" in staged["principles"] or clean_name in staged["principles"]:
            results_table.add_row(clean_name, "principle", "-", "[dim]Skipped (Already Staged)[/dim]")
            skipped_count += 1
            continue

        if not dry_run:
            try:
                stage_principle(src, f"{clean_name}.md", overwrite=False)
                results_table.add_row(clean_name, "principle", "-", "[green]Staged[/green]")
                staged_count += 1
            except Exception as exc:
                results_table.add_row(clean_name, "principle", "-", f"[red]Failed ({exc})[/red]")
        else:
            results_table.add_row(clean_name, "principle", "-", "[yellow]Would Stage (Dry Run)[/yellow]")

    # Process Workflows
    for src, override_name in workflows_to_import:
        if not src.exists():
            continue
        item_name = override_name if override_name else extract_name_from_source(src, name_source)
        clean_name = normalize_name(item_name)

        if f"{clean_name}.md" in staged["workflows"] or clean_name in staged["workflows"]:
            results_table.add_row(clean_name, "workflow", "-", "[dim]Skipped (Already Staged)[/dim]")
            skipped_count += 1
            continue

        if not dry_run:
            try:
                stage_workflow(src, f"{clean_name}.md", overwrite=False)
                results_table.add_row(clean_name, "workflow", "-", "[green]Staged[/green]")
                staged_count += 1
            except Exception as exc:
                results_table.add_row(clean_name, "workflow", "-", f"[red]Failed ({exc})[/red]")
        else:
            results_table.add_row(clean_name, "workflow", "-", "[yellow]Would Stage (Dry Run)[/yellow]")

    console.print(results_table)
    if dry_run:
        console.print("[yellow]Dry run complete. No files were modified.[/yellow]")
    else:
        console.print(f"[bold green]Import complete: {staged_count} staged, {skipped_count} skipped.[/bold green]")


@cli.command(name="remove")
@click.argument("args", nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Bypass confirmation prompt")
def remove_cmd(args, yes):
    """Remove item(s) from staging hub and purge symlinks & overrides across agents."""
    explicit_type, names = _resolve_item_type(args)
    if not names:
        console.print("[red]Error: Please specify one or more item names to remove.[/red]")
        return

    staged = get_staged_items()

    for name in names:
        clean_name = normalize_name(name)
        staged_types = get_staged_types_for_item(clean_name)

        if not staged_types:
            console.print(f"[red]Error: '{clean_name}' is not staged.[/red]")
            continue

        target_type = explicit_type
        if explicit_type and explicit_type not in staged_types:
            console.print(f"[red]Error: '{clean_name}' is staged as {', '.join(staged_types)}, not as a {explicit_type}.[/red]")
            continue

        if not explicit_type and len(staged_types) > 1:
            console.print(f"[yellow]'{clean_name}' is staged as multiple types:[/yellow]")
            options = staged_types + ["all"]
            for idx, opt in enumerate(options, 1):
                console.print(f"  {idx}) {opt}")
            choice = click.prompt("Select type to remove", type=int, default=1)
            chosen_opt = options[choice - 1]
            target_type = None if chosen_opt == "all" else chosen_opt

        if not yes:
            if not click.confirm(f"Are you sure you want to remove '{clean_name}'?"):
                console.print("[yellow]Aborted.[/yellow]")
                continue

        removed_types = remove_staged_item(clean_name, target_type)
        if removed_types:
            console.print(f"[bold green]Removed '{clean_name}' ({', '.join(removed_types)}) from hub & agents.[/bold green]")
        else:
            console.print(f"[yellow]No items removed for '{clean_name}'.[/yellow]")


@cli.command()
@click.argument("args", nargs=-1, required=True)
@click.option("--global/--local", "is_global", default=False, help="Enable globally or locally")
@click.option("--agent", multiple=True, help="Target specific agent(s)")
def enable(args, is_global, agent):
    """Enable one or more skills/principles/workflows for agents."""
    is_global = _resolve_scope(is_global)
    explicit_type, names = _resolve_item_type(args)
    if not names:
        console.print("[red]Error: Please specify one or more names to enable.[/red]")
        return

    staged = get_staged_items()
    agents_to_target = _resolve_agents_to_target(agent)

    for name in names:
        item_type, staged_name = _detect_staged_item_type(name, staged, explicit_type)
        if not item_type:
            continue

        clean_name = normalize_name(name)
        staged_types = get_staged_types_for_item(clean_name)
        types_to_enable = staged_types if item_type == "all" else [item_type]

        for t in types_to_enable:
            cur_staged_name = f"{clean_name}.md" if t in ("principle", "workflow") else clean_name
            src_path = axon.core.AXON_DIR / f"{t}s" / cur_staged_name

            if not src_path.exists():
                console.print(f"[red]Error: Staged path {src_path} does not exist.[/red]")
                continue

            for ag in agents_to_target:
                if ag not in ADAPTERS:
                    console.print(f"[yellow]Warning: Unknown agent '{ag}'. Skipping.[/yellow]")
                    continue
                adapter = ADAPTERS[ag]

                if t == "skill" and not adapter.supports_skills:
                    console.print(
                        f"[yellow]Skipping {adapter.name}: does not support discrete skill files.[/yellow]"
                    )
                    continue
                if t == "workflow" and not adapter.local_workflow_dirs:
                    console.print(
                        f"[yellow]Skipping {adapter.name}: does not have workflow directories.[/yellow]"
                    )
                    continue

                target_dirs = adapter.get_dir_paths(t, is_global=is_global)
                scope = "global" if is_global else "local"

                if is_global and not target_dirs:
                    console.print(
                        f"[yellow]Warning: {adapter.name} has no global {t} dirs. "
                        f"Falling back to local.[/yellow]"
                    )
                    target_dirs = adapter.get_dir_paths(t, is_global=False)
                    scope = "local"

                if not target_dirs:
                    continue

                # Remove stale files in OPPOSITE dirs (skill→principles, principle→skills)
                for opp_dir in adapter.get_opposite_dir_paths(t, is_global=(scope == "global")):
                    for candidate in [clean_name, f"{clean_name}.mdc", f"{clean_name}.md"]:
                        stale = opp_dir / candidate
                        if stale.is_symlink() or stale.is_file():
                            stale.unlink()
                        elif stale.is_dir():
                            shutil.rmtree(stale)

                dest_name = _dest_name_for(cur_staged_name, adapter, t)

                enabled_in_any = False
                for target_dir in target_dirs:
                    ok = _do_enable_item(src_path, target_dir, dest_name, adapter, t)
                    if ok:
                        enabled_in_any = True

                if enabled_in_any or (t == "principle" and adapter.supports_compile):
                    if enabled_in_any:
                        console.print(f"[green]Enabled '{clean_name}' ({t}) in {adapter.name} ({scope})[/green]")
                    update_config_state(ag, scope, f"{t}s", clean_name, enable=True)
                    if t == "principle":
                        compile_principles_for_agent(ag, scope)


@cli.command()
@click.argument("args", nargs=-1, required=True)
@click.option("--global/--local", "is_global", default=False, help="Disable globally or locally")
@click.option("--agent", multiple=True, help="Target specific agent(s)")
def disable(args, is_global, agent):
    """Disable one or more skills/principles/workflows."""
    is_global = _resolve_scope(is_global)
    explicit_type, names = _resolve_item_type(args)
    if not names:
        console.print("[red]Error: Please specify one or more names to disable.[/red]")
        return

    staged = get_staged_items()
    agents_to_target = _resolve_agents_to_target(agent)

    for name in names:
        item_type, staged_name = _detect_staged_item_type(name, staged, explicit_type)
        if not item_type:
            continue

        clean_name = normalize_name(name)
        staged_types = get_staged_types_for_item(clean_name)
        types_to_disable = staged_types if item_type == "all" else [item_type]

        for t in types_to_disable:
            cur_staged_name = f"{clean_name}.md" if t in ("principle", "workflow") else clean_name
            src_path = axon.core.AXON_DIR / f"{t}s" / cur_staged_name

            for ag in agents_to_target:
                if ag not in ADAPTERS:
                    continue
                adapter = ADAPTERS[ag]
                scope = "global" if is_global else "local"
                target_dirs = adapter.get_dir_paths(t, is_global=is_global)
                dest_name = _dest_name_for(cur_staged_name, adapter, t)

                removed_any = False
                for target_dir in target_dirs:
                    if _do_disable_item(target_dir, dest_name, item_type=t, src_path=src_path):
                        removed_any = True

                if removed_any:
                    console.print(f"[yellow]Disabled '{clean_name}' ({t}) in {adapter.name} ({scope})[/yellow]")
                update_config_state(ag, scope, f"{t}s", clean_name, enable=False)
                if t == "principle":
                    compile_principles_for_agent(ag, scope)


@cli.command()
@click.argument("item_type_or_name", required=False)
@click.argument("names", nargs=-1)
@click.option("--global/--local", "is_global", default=False, help="Activate globally or locally")
@click.option("--agent", multiple=True, help="Target specific agent(s)")
def activate(item_type_or_name, names, is_global, agent):
    """Enable model auto-invocation for one or more skills/principles."""
    _toggle_auto_invocation_cmd(item_type_or_name, names, is_global, agent, enable_auto=True)


@cli.command()
@click.argument("item_type_or_name", required=False)
@click.argument("names", nargs=-1)
@click.option("--global/--local", "is_global", default=False, help="Deactivate globally or locally")
@click.option("--agent", multiple=True, help="Target specific agent(s)")
def deactivate(item_type_or_name, names, is_global, agent):
    """Disable model auto-invocation for one or more skills/principles."""
    _toggle_auto_invocation_cmd(item_type_or_name, names, is_global, agent, enable_auto=False)


def _toggle_auto_invocation_cmd(item_type_or_name, names, is_global, agent, enable_auto: bool):
    is_global = _resolve_scope(is_global)
    staged = get_staged_items()
    explicit_type = None
    all_names = []

    if item_type_or_name:
        if item_type_or_name.lower() in ("skill", "principle", "workflow"):
            explicit_type = item_type_or_name.lower()
            all_names = list(names)
        else:
            all_names = [item_type_or_name] + list(names)

    if not all_names:
        console.print("[red]Error: Please specify at least one item to toggle auto-invocation for.[/red]")
        return

    agents_to_target = _resolve_agents_to_target(agent)
    status_str = "ON" if enable_auto else "OFF"
    action_str = "Activated" if enable_auto else "Deactivated"

    for name in all_names:
        clean_name = normalize_name(name)
        item_type, _ = _detect_staged_item_type(clean_name, staged, explicit_type)
        if not item_type:
            item_type = "skill"

        src_path = axon.core.AXON_DIR / f"{item_type}s" / clean_name
        if item_type in ("principle", "workflow"):
            src_path = axon.core.AXON_DIR / f"{item_type}s" / f"{clean_name}.md"

        if is_global:
            if src_path.exists():
                set_auto_invocation(src_path, enable_auto)
            console.print(f"[bold green]{action_str} '{clean_name}' globally (auto-invocation: {status_str})[/bold green]")

            for ag in agents_to_target:
                if ag not in ADAPTERS:
                    continue
                adapter = ADAPTERS[ag]
                scope = "global"
                target_dirs = adapter.get_dir_paths(item_type, is_global=True)
                dest_name = _dest_name_for(clean_name, adapter, item_type)

                if item_type == "skill" and adapter.skill_format in (SKILL_FORMAT_FLAT_MDC, SKILL_FORMAT_FLAT_MD):
                    base_src = src_path / "SKILL.md"
                else:
                    base_src = src_path

                for target_dir in target_dirs:
                    dest_path = target_dir / dest_name
                    if dest_path.exists():
                        ensure_local_target(base_src, dest_path, require_copy=False)
                        update_config_state(ag, scope, f"{item_type}s", clean_name, enable=True)
        else:
            for ag in agents_to_target:
                if ag not in ADAPTERS:
                    continue
                adapter = ADAPTERS[ag]
                scope = "local"
                target_dirs = adapter.get_dir_paths(item_type, is_global=False)
                dest_name = _dest_name_for(clean_name, adapter, item_type)

                if item_type == "skill" and adapter.skill_format in (SKILL_FORMAT_FLAT_MDC, SKILL_FORMAT_FLAT_MD):
                    base_src = src_path / "SKILL.md"
                else:
                    base_src = src_path

                base_auto = get_auto_invocation_status(base_src)
                need_override = (enable_auto != base_auto)

                for target_dir in target_dirs:
                    dest_path = target_dir / dest_name
                    if need_override:
                        ensure_local_target(base_src, dest_path, require_copy=True)
                        set_auto_invocation(dest_path, enable_auto)
                    else:
                        if dest_path.exists() and not dest_path.is_symlink():
                            set_auto_invocation(dest_path, enable_auto)
                        ensure_local_target(base_src, dest_path, require_copy=False)

                    is_override = not dest_path.is_symlink()
                    storage_str = "local override" if is_override else "symlink"
                    console.print(f"[green]{action_str} '{clean_name}' in {adapter.name} ({scope}, auto-invocation: {status_str}, {storage_str})[/green]")
                    update_config_state(ag, scope, f"{item_type}s", clean_name, enable=True)


@cli.command()
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
def sync(yes):
    """Rebuild all symlinks from config.yaml (hard reset)."""
    if not yes:
        console.print(
            "[bold red]Warning: This will forcefully recreate all symlinks from config.yaml.[/bold red]"
        )
        if not click.confirm("Proceed?"):
            console.print("Sync aborted.")
            return

    config = load_config()
    for ag, scopes in config.get("agents", {}).items():
        if ag not in ADAPTERS:
            continue
        adapter = ADAPTERS[ag]

        for scope, item_types in scopes.items():
            is_glob = scope == "global"
            for item_type_key, names in item_types.items():
                item_type = item_type_key.rstrip("s")
                target_dirs = adapter.get_dir_paths(item_type, is_global=is_glob)

                for name in names:
                    clean_name = normalize_name(name)
                    staged_name = f"{clean_name}.md" if item_type in ("principle", "workflow") else clean_name
                    src_path = axon.core.AXON_DIR / f"{item_type}s" / staged_name
                    if not src_path.exists():
                        console.print(
                            f"[yellow]Warning: Staged source for '{clean_name}' not found. Skipping.[/yellow]"
                        )
                        continue

                    dest_name = _dest_name_for(clean_name, adapter, item_type)

                    synced_any = False
                    for target_dir in target_dirs:
                        ok = _do_enable_item(src_path, target_dir, dest_name, adapter, item_type)
                        if ok:
                            synced_any = True

                    if synced_any:
                        console.print(
                            f"[green]Synced '{clean_name}' ({item_type}) in {adapter.name} ({scope})[/green]"
                        )

            compile_principles_for_agent(ag, scope)

    console.print("[bold green]Sync complete.[/bold green]")
