import click
import shutil
import subprocess
import sys
import os
from importlib.metadata import version as pkg_version, PackageNotFoundError
from rich.console import Console
from pathlib import Path
from axon.adapters import (
    ADAPTERS,
    scaffold_local_env,
    SKILL_FORMAT_FOLDER,
    SKILL_FORMAT_FLAT_MDC,
    SKILL_FORMAT_FLAT_MD,
    SKILL_FORMAT_NONE,
)
from axon.core import (
    get_staged_items,
    load_config,
    AXON_DIR,
    update_config_state,
    init_axon_dir,
    stage_skill,
    stage_principle,
    stage_workflow,
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
        # flat file: add extension if not already present
        return name if name.endswith(suffix) else f"{name}{suffix}"
    else:
        # principles and workflows are always flat .md files
        return name if name.endswith(".md") else f"{name}.md"


def _do_enable_link(
    src_path: Path,
    target_dir: Path,
    dest_name: str,
    adapter,
    item_type: str,
) -> bool:
    """
    Create the appropriate link/copy in target_dir for src_path.
    For folder_skill_md agents: symlink the whole folder.
    For flat file agents: symlink the SKILL.md file (or the flat file itself).
    Returns True on success.
    """
    if not target_dir.exists():
        return False

    dest_path = target_dir / dest_name

    # Remove existing symlink so we can re-point it
    if dest_path.is_symlink():
        dest_path.unlink()
    elif dest_path.exists():
        console.print(f"[yellow]Warning: {dest_path} exists and is not a symlink. Skipping.[/yellow]")
        return False

    if item_type == "skill" and adapter.uses_skill_folders:
        # src_path is ~/.axon/skills/<name> (a folder); symlink the whole folder
        if not src_path.is_dir():
            console.print(f"[red]Error: Staged skill '{src_path.name}' is not a folder. "
                          f"Re-stage it with 'axon add'.[/red]")
            return False
        os.symlink(src_path, dest_path)
    elif item_type == "skill" and adapter.skill_format in (SKILL_FORMAT_FLAT_MDC, SKILL_FORMAT_FLAT_MD):
        # src_path is ~/.axon/skills/<name>  (a folder in staging hub);
        # for flat-file agents symlink the SKILL.md file inside it.
        skill_md = src_path / "SKILL.md"
        if not skill_md.exists():
            console.print(f"[red]Error: No SKILL.md found inside staged skill '{src_path.name}'.[/red]")
            return False
        os.symlink(skill_md, dest_path)
    else:
        # Principles and workflows are always flat files in staging hub
        if src_path.is_dir():
            console.print(f"[red]Error: Staged {item_type} '{src_path.name}' is a folder, "
                          f"but {item_type}s must be flat files.[/red]")
            return False
        os.symlink(src_path, dest_path)

    return True


def _do_disable_link(target_dir: Path, dest_name: str) -> bool:
    """Remove a symlink from target_dir. Returns True if something was removed."""
    dest_path = target_dir / dest_name
    if dest_path.is_symlink():
        dest_path.unlink()
        return True
    elif dest_path.exists():
        console.print(f"[yellow]Warning: '{dest_path}' is not a symlink. Skipping deletion.[/yellow]")
    return False


# ─────────────────────────────────────────────────────────
# CLI commands
# ─────────────────────────────────────────────────────────

@click.group()
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
    """Update Axon CLI to the latest (or a specific) version.

    This upgrades the package in-place inside the same isolated venv
    that install.sh created (~/.axon-env).

    Examples:
      axon update
      axon update --version v0.2.0
    """
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
        console.print("Try re-running the installer:\n")
        console.print(f"  [dim]curl -sSL https://raw.githubusercontent.com/aayushlalroy/axon/main/install.sh | bash[/dim]")
        return

    new_version = _get_installed_version()
    if new_version != current:
        console.print(f"[bold green]✓ Updated:[/bold green] {current} → {new_version}")
    else:
        console.print(f"[bold green]✓ Already up to date:[/bold green] {new_version}")


@cli.command()
@click.option("--agent", multiple=True, help="Specify agents to initialize (cursor, claude, gemini, …)")
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
            console.print(f"  - {s}")
        console.print("\n[bold]Principles:[/bold]")
        for p in staged["principles"]:
            console.print(f"  - {p}")
        console.print("\n[bold]Workflows:[/bold]")
        for w in staged["workflows"]:
            console.print(f"  - {w}")
        return

    config = load_config()
    console.print("[bold cyan]Currently Enabled Items:[/bold cyan]")
    agents_to_list = [agent] if agent else ADAPTERS.keys()

    for ag in agents_to_list:
        if ag not in ADAPTERS:
            continue
        console.print(f"\n[bold underline]{ADAPTERS[ag].name}[/bold underline]")
        agent_config = config.get("agents", {}).get(ag, {})

        for scope_label in ("local", "global"):
            scope_cfg = agent_config.get(scope_label, {})
            skills = scope_cfg.get("skills", [])
            principles = scope_cfg.get("principles", [])
            workflows = scope_cfg.get("workflows", [])
            if not skills and not principles and not workflows:
                continue
            console.print(f"  [bold]{scope_label.capitalize()}:[/bold]")
            if skills:
                console.print("    [bold]Skills:[/bold]")
                for s in skills:
                    console.print(f"      - {s}")
            if principles:
                console.print("    [bold]Principles:[/bold]")
                for p in principles:
                    console.print(f"      - {p}")
            if workflows:
                console.print("    [bold]Workflows:[/bold]")
                for w in workflows:
                    console.print(f"      - {w}")

        # If nothing printed for either scope
        local_empty = not agent_config.get("local")
        global_empty = not agent_config.get("global")
        if local_empty and global_empty:
            console.print("  [dim]No items enabled.[/dim]")


@cli.command()
@click.argument("source_path", type=click.Path(exists=True))
@click.option("--name", help="Override the default staged name")
@click.option(
    "--type", "item_type",
    type=click.Choice(["skill", "principle", "workflow"]),
    help="Force the item type (skips interactive prompt)",
)
def add(source_path, name, item_type):
    """Stage a skill, principle, or workflow into the ~/.axon hub.

    Skills are always stored as <name>/SKILL.md folders in the hub,
    regardless of the source format. This ensures they are compatible
    with all folder_skill_md agents and can be adapted for flat-file agents.
    """
    init_axon_dir()
    src = Path(source_path)
    item_name = name if name else src.stem  # strip extension for clean name

    if not item_type:
        item_type = click.prompt(
            "What type? [skill / principle / workflow]",
            type=click.Choice(["skill", "principle", "workflow"]),
        )

    try:
        if item_type == "skill":
            dest = stage_skill(src, item_name, overwrite=False)
        elif item_type == "principle":
            dest = stage_principle(src, item_name + (".md" if not item_name.endswith(".md") else ""), overwrite=False)
        else:
            dest = stage_workflow(src, item_name + (".md" if not item_name.endswith(".md") else ""), overwrite=False)
    except FileExistsError:
        console.print(f"[yellow]Warning: '{item_name}' already staged.[/yellow]")
        if not click.confirm("Overwrite?"):
            console.print("[yellow]Aborted.[/yellow]")
            return
        if item_type == "skill":
            dest = stage_skill(src, item_name, overwrite=True)
        elif item_type == "principle":
            dest = stage_principle(src, item_name + (".md" if not item_name.endswith(".md") else ""), overwrite=True)
        else:
            dest = stage_workflow(src, item_name + (".md" if not item_name.endswith(".md") else ""), overwrite=True)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    console.print(f"[bold green]Staged '{item_name}' ({item_type}) → {dest}[/bold green]")
    console.print("[dim]Use 'axon enable' to activate it for an agent.[/dim]")


@cli.command()
@click.argument("args", nargs=-1, required=True)
@click.option("--global/--local", "is_global", default=False, help="Enable globally or locally")
@click.option("--agent", help="Target specific agent (e.g. cursor)")
def enable(args, is_global, agent):
    """Enable one or more skills/principles/workflows for agents.

    Usage examples:
      axon enable my-skill
      axon enable skill my-skill
      axon enable principle coding-style
      axon enable workflow pr-review
      axon enable my-skill --agent cursor
      axon enable my-skill --global
    """
    explicit_type, names = _resolve_item_type(args)
    if not names:
        console.print("[red]Error: Please specify one or more names to enable.[/red]")
        return

    staged = get_staged_items()
    agents_to_target = [agent] if agent else list(ADAPTERS.keys())

    for name in names:
        # Auto-detect item type if not explicit
        item_type = explicit_type
        if not item_type:
            if name in staged["skills"]:
                item_type = "skill"
            elif name in staged["principles"] or (name + ".md") in staged["principles"]:
                item_type = "principle"
            elif name in staged["workflows"] or (name + ".md") in staged["workflows"]:
                item_type = "workflow"
            else:
                console.print(
                    f"[red]Error: '{name}' is not staged. "
                    f"Use 'axon add' first.[/red]"
                )
                continue

        # Resolve actual staged name (with possible .md suffix for principles/workflows)
        staged_name = name
        if item_type in ("principle", "workflow"):
            staged_name = name if name.endswith(".md") else name  # stored in staging as-is
            # check both variants
            bucket = staged[f"{item_type}s"]
            if name not in bucket and f"{name}.md" in bucket:
                staged_name = f"{name}.md"

        src_path = AXON_DIR / f"{item_type}s" / staged_name

        if not src_path.exists():
            console.print(f"[red]Error: Staged path {src_path} does not exist.[/red]")
            continue

        for ag in agents_to_target:
            if ag not in ADAPTERS:
                console.print(f"[yellow]Warning: Unknown agent '{ag}'. Skipping.[/yellow]")
                continue
            adapter = ADAPTERS[ag]

            # Edge case: agent doesn't support this item type
            if item_type == "skill" and not adapter.supports_skills:
                console.print(
                    f"[yellow]Skipping {adapter.name}: does not support discrete skill files.[/yellow]"
                )
                continue
            if item_type == "workflow" and not adapter.local_workflow_dirs:
                console.print(
                    f"[yellow]Skipping {adapter.name}: does not have workflow directories.[/yellow]"
                )
                continue

            target_dirs = adapter.get_dir_paths(item_type, is_global=is_global)
            scope = "global" if is_global else "local"

            # Fallback: global requested but agent has no global dirs
            if is_global and not target_dirs:
                console.print(
                    f"[yellow]Warning: {adapter.name} has no global {item_type} dirs. "
                    f"Falling back to local.[/yellow]"
                )
                target_dirs = adapter.get_dir_paths(item_type, is_global=False)
                scope = "local"

            if not target_dirs:
                console.print(
                    f"[yellow]Skipping {adapter.name}: no target directories for {item_type}s.[/yellow]"
                )
                continue

            # Remove stale symlinks in OPPOSITE dirs (skill→principles, principle→skills)
            for opp_dir in adapter.get_opposite_dir_paths(item_type, is_global=(scope == "global")):
                for candidate in [name, f"{name}.mdc", f"{name}.md"]:
                    stale = opp_dir / candidate
                    if stale.is_symlink():
                        stale.unlink()

            dest_name = _dest_name_for(name, adapter, item_type)

            enabled_in_any = False
            for target_dir in target_dirs:
                # Create target dir if missing
                if not target_dir.exists():
                    console.print(
                        f"[yellow]Directory {target_dir} is missing. Creating it.[/yellow]"
                    )
                    target_dir.mkdir(parents=True, exist_ok=True)

                ok = _do_enable_link(src_path, target_dir, dest_name, adapter, item_type)
                if ok:
                    enabled_in_any = True

            # Report + record once per agent, not once per target directory
            if enabled_in_any:
                console.print(
                    f"[green]Enabled '{name}' ({item_type}) in {adapter.name} ({scope})[/green]"
                )
                update_config_state(ag, scope, f"{item_type}s", name, enable=True)


@cli.command()
@click.argument("args", nargs=-1, required=True)
@click.option("--global/--local", "is_global", default=False, help="Disable globally or locally")
@click.option("--agent", help="Target specific agent (e.g. cursor)")
def disable(args, is_global, agent):
    """Disable one or more skills/principles/workflows.

    Usage examples:
      axon disable my-skill
      axon disable skill my-skill
      axon disable principle coding-style
    """
    explicit_type, names = _resolve_item_type(args)
    if not names:
        console.print("[red]Error: Please specify one or more names to disable.[/red]")
        return

    staged = get_staged_items()
    agents_to_target = [agent] if agent else list(ADAPTERS.keys())

    for name in names:
        item_type = explicit_type
        if not item_type:
            if name in staged["skills"]:
                item_type = "skill"
            elif name in staged["principles"] or f"{name}.md" in staged["principles"]:
                item_type = "principle"
            elif name in staged["workflows"] or f"{name}.md" in staged["workflows"]:
                item_type = "workflow"
            else:
                # Item may be enabled but un-staged; fall back to checking all dirs
                item_type = "skill"  # safe default; will attempt all dirs

        # Warn if explicit type doesn't match staging
        if explicit_type:
            other_types = [t for t in ("skill", "principle", "workflow") if t != explicit_type]
            for other in other_types:
                bucket = staged[f"{other}s"]
                if name in bucket or f"{name}.md" in bucket:
                    if name not in staged[f"{explicit_type}s"] and f"{name}.md" not in staged[f"{explicit_type}s"]:
                        console.print(
                            f"[yellow]Warning: '{name}' is staged as a {other}, "
                            f"not a {explicit_type}. Skipping.[/yellow]"
                        )
                        item_type = None
                        break

        if item_type is None:
            continue

        for ag in agents_to_target:
            if ag not in ADAPTERS:
                continue
            adapter = ADAPTERS[ag]

            scope = "global" if is_global else "local"
            target_dirs = adapter.get_dir_paths(item_type, is_global=is_global)

            dest_name = _dest_name_for(name, adapter, item_type)

            removed_any = False
            for target_dir in target_dirs:
                if _do_disable_link(target_dir, dest_name):
                    removed_any = True

            # Report + update config once per agent, not once per target directory
            if removed_any:
                console.print(f"[yellow]Disabled '{name}' ({item_type}) in {adapter.name} ({scope})[/yellow]")
            update_config_state(ag, scope, f"{item_type}s", name, enable=False)


@cli.command()
def sync():
    """Rebuild all symlinks from config.yaml (hard reset)."""
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
                # Normalise 'skills' → 'skill'
                item_type = item_type_key.rstrip("s")
                target_dirs = adapter.get_dir_paths(item_type, is_global=is_glob)

                for name in names:
                    src_path = AXON_DIR / f"{item_type}s" / name
                    if not src_path.exists():
                        console.print(
                            f"[yellow]Warning: Staged source for '{name}' not found. Skipping.[/yellow]"
                        )
                        continue

                    dest_name = _dest_name_for(name, adapter, item_type)

                    # Clean stale opposite-type symlinks
                    for opp_dir in adapter.get_opposite_dir_paths(item_type, is_global=is_glob):
                        for candidate in [name, f"{name}.mdc", f"{name}.md"]:
                            stale = opp_dir / candidate
                            if stale.is_symlink():
                                stale.unlink()

                    synced_any = False
                    for target_dir in target_dirs:
                        if not target_dir.exists():
                            target_dir.mkdir(parents=True, exist_ok=True)
                        ok = _do_enable_link(src_path, target_dir, dest_name, adapter, item_type)
                        if ok:
                            synced_any = True

                    # Print once per agent/item, not once per target dir
                    if synced_any:
                        console.print(
                            f"[green]Synced '{name}' ({item_type}) in {adapter.name} ({scope})[/green]"
                        )

    console.print("[bold green]Sync complete.[/bold green]")
