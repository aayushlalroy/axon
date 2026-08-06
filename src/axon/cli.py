import click
import shutil
import os
from rich.console import Console
from pathlib import Path
from axon.adapters import ADAPTERS, scaffold_local_env
from axon.core import get_staged_items, load_config, AXON_DIR, update_config_state, init_axon_dir

console = Console()

@click.group()
def cli():
    """Axon: Skill & Constitution Management System for AI Agents"""
    pass

@cli.command()
def agents():
    """List all currently supported agent adapters."""
    console.print("[bold green]Supported Agent Adapters:[/bold green]")
    console.print("- Cursor [dim](.cursor/rules/, .cursorrules)[/dim]")
    console.print("- Claude Code [dim](CLAUDE.md)[/dim]")
    console.print("- Gemini/Antigravity [dim](~/.gemini/config/, .agents/)[/dim]")
    console.print("- Devin [dim](AGENTS.md, .agents/skills/)[/dim]")
    console.print("- Codex [dim](AGENTS.md, .codex/skills/)[/dim]")

@cli.command()
@click.option('--agent', multiple=True, help="Specify agents to initialize (cursor, claude, gemini)")
def init(agent):
    """Initialize current project folder for agents."""
    agents_to_init = agent if agent else ADAPTERS.keys()
    
    for ag in agents_to_init:
        if ag not in ADAPTERS:
            console.print(f"[yellow]Warning: Agent '{ag}' is not supported.[/yellow]")
            continue
        
        console.print(f"Initializing {ADAPTERS[ag].name}...")
        scaffold_local_env(ag)
        
    console.print("[bold green]Initialization complete.[/bold green]")
    console.print("[dim]Note: Consider whether you want to track these directories in git or add them to .gitignore (V2 feature).[/dim]")

@cli.command(name="list")
@click.option('--all', 'show_all', is_flag=True, help="List all available staged items.")
@click.option('--agent', help="Filter by specific agent (cursor, claude, gemini)")
def list_items(show_all, agent):
    """List skills and principles (enabled or all)."""
    staged = get_staged_items()
    if show_all:
        console.print("[bold cyan]All Staged Items in ~/.axon:[/bold cyan]")
        console.print("[bold]Skills:[/bold]")
        for s in staged["skills"]:
            console.print(f"  - {s}")
        console.print("\n[bold]Principles:[/bold]")
        for p in staged["principles"]:
            console.print(f"  - {p}")
        return

    config = load_config()
    console.print("[bold cyan]Currently Enabled Items:[/bold cyan]")
    
    agents_to_list = [agent] if agent else ADAPTERS.keys()
    
    for ag in agents_to_list:
        if ag not in ADAPTERS:
            continue
        console.print(f"\n[bold underline]{ADAPTERS[ag].name}[/bold underline]")
        
        agent_config = config.get("agents", {}).get(ag, {})
        
        local_skills = agent_config.get("local", {}).get("skills", [])
        global_skills = agent_config.get("global", {}).get("skills", [])
        local_principles = agent_config.get("local", {}).get("principles", [])
        global_principles = agent_config.get("global", {}).get("principles", [])
        
        if not local_skills and not global_skills and not local_principles and not global_principles:
            console.print("  [dim]No items enabled.[/dim]")
            continue
            
        if local_skills or local_principles:
            console.print("  [bold]Local:[/bold]")
            if local_skills:
                console.print("    [bold]Skills:[/bold]")
                for s in local_skills:
                    console.print(f"      - {s}")
            if local_principles:
                console.print("    [bold]Principles:[/bold]")
                for p in local_principles:
                    console.print(f"      - {p}")

        if global_skills or global_principles:
            console.print("  [bold]Global:[/bold]")
            if global_skills:
                console.print("    [bold]Skills:[/bold]")
                for s in global_skills:
                    console.print(f"      - {s}")
            if global_principles:
                console.print("    [bold]Principles:[/bold]")
                for p in global_principles:
                    console.print(f"      - {p}")

@cli.command()
@click.argument('source_path', type=click.Path(exists=True))
@click.option('--name', help="Override the default name")
def add(source_path, name):
    """Launch interactive wizard to stage a new skill or principle."""
    init_axon_dir()
    src = Path(source_path)
    item_name = name if name else src.name
    
    console.print(f"[bold]Staging {src}[/bold]")
    item_type = click.prompt(
        "Is this a [1] Skill (On-Demand) or [2] Principle (Always On)?", 
        type=click.Choice(['1', '2'])
    )
    
    dest_dir = AXON_DIR / ("skills" if item_type == '1' else "principles")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / item_name
    
    if dest_path.exists():
        console.print(f"[yellow]Warning: '{item_name}' already exists in staging.[/yellow]")
        if not click.confirm("Do you want to overwrite it?"):
            console.print("[yellow]Aborted.[/yellow]")
            return
            
    if click.confirm(f"Confirm staging '{item_name}' into {dest_dir}?"):
        if src.is_dir():
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(src, dest_path)
        else:
            shutil.copy2(src, dest_path)
        console.print(f"[bold green]Successfully staged '{item_name}'.[/bold green]")
        console.print("[dim]Use 'axon enable' to activate it.[/dim]")

def _resolve_item_type(arg_list, command_name="enable"):
    """Parse positional arguments to detect explicit item_type or auto-detect from staging."""
    if not arg_list:
        return None, []
    
    first = arg_list[0].lower()
    if first in ['skill', 'skills', 'principle', 'principles']:
        explicit_type = 'skill' if first.startswith('skill') else 'principle'
        return explicit_type, list(arg_list[1:])
    else:
        return None, list(arg_list)

@cli.command()
@click.argument('args', nargs=-1, required=True)
@click.option('--global/--local', 'is_global', default=False, help="Enable globally or locally")
@click.option('--agent', help="Target specific agent (e.g. cursor)")
def enable(args, is_global, agent):
    """Enable one or more skills/principles. Auto-detects staged type if omitted."""
    explicit_type, names = _resolve_item_type(args, "enable")
    if not names:
        console.print("[red]Error: Please specify one or more skill/principle names to enable.[/red]")
        return

    staged = get_staged_items()
    agents_to_target = [agent] if agent else ADAPTERS.keys()
    
    for name in names:
        item_type = explicit_type
        if not item_type:
            if name in staged["principles"]:
                item_type = "principle"
            elif name in staged["skills"]:
                item_type = "skill"
            else:
                console.print(f"[red]Error: '{name}' is not staged as a skill or principle in ~/.axon.[/red]")
                continue

        valid_items = staged[f"{item_type}s"]
        if name not in valid_items:
            console.print(f"[red]Error: '{name}' is staged as a {'skill' if item_type == 'principle' else 'principle'}, not a {item_type}.[/red]")
            continue
            
        src_path = AXON_DIR / f"{item_type}s" / name
        
        for ag in agents_to_target:
            if ag not in ADAPTERS:
                continue
            adapter = ADAPTERS[ag]
            
            target_dirs = adapter.get_dir_paths(item_type, is_global=is_global)
            scope = "global" if is_global else "local"
            
            if is_global and not target_dirs:
                console.print(f"[yellow]Warning: {adapter.name} does not support global file-based {item_type}s. Falling back to local.[/yellow]")
                target_dirs = adapter.get_dir_paths(item_type, is_global=False)
                scope = "local"
            
            # Clean up any stale symlinks of this item from opposite type directories
            opposite_dirs = adapter.get_opposite_dir_paths(item_type, is_global=(scope == "global"))
            for opp_dir in opposite_dirs:
                stale_symlink = opp_dir / name
                if stale_symlink.exists() and stale_symlink.is_symlink():
                    stale_symlink.unlink()
                
            for target_dir in target_dirs:
                if not target_dir.exists():
                    console.print(f"[yellow]Warning: Directory {target_dir} is missing.[/yellow]")
                    if click.confirm("Do you want to create it?"):
                        target_dir.mkdir(parents=True, exist_ok=True)
                    else:
                        continue
                
                dest_path = target_dir / name
                if dest_path.exists():
                    if dest_path.is_symlink():
                        dest_path.unlink()
                    else:
                        console.print(f"[yellow]Warning: {dest_path} exists and is not a symlink. Skipping.[/yellow]")
                        continue
                
                os.symlink(src_path, dest_path)
                console.print(f"[green]Enabled '{name}' in {adapter.name} ({scope})[/green]")
                update_config_state(ag, scope, f"{item_type}s", name, enable=True)


@cli.command()
@click.argument('args', nargs=-1, required=True)
@click.option('--global/--local', 'is_global', default=False, help="Disable globally or locally")
@click.option('--agent', help="Target specific agent (e.g. cursor)")
def disable(args, is_global, agent):
    """Disable one or more skills/principles. Auto-detects staged type if omitted."""
    explicit_type, names = _resolve_item_type(args, "disable")
    if not names:
        console.print("[red]Error: Please specify one or more skill/principle names to disable.[/red]")
        return

    staged = get_staged_items()
    agents_to_target = [agent] if agent else ADAPTERS.keys()
    
    for name in names:
        item_type = explicit_type
        if not item_type:
            if name in staged["principles"]:
                item_type = "principle"
            elif name in staged["skills"]:
                item_type = "skill"
            else:
                # Fallback to checking config if un-staged
                item_type = "principle"

        # Verify that explicit type matches staging
        if explicit_type:
            other_type = "skill" if explicit_type == "principle" else "principle"
            if name in staged[f"{other_type}s"] and name not in staged[f"{explicit_type}s"]:
                console.print(f"[yellow]Warning: '{name}' is staged as a {other_type}, not a {explicit_type}. Skipping.[/yellow]")
                continue

        for ag in agents_to_target:
            if ag not in ADAPTERS:
                continue
            adapter = ADAPTERS[ag]
            
            target_dirs = adapter.get_dir_paths(item_type, is_global=is_global)
            scope = "global" if is_global else "local"
            
            for target_dir in target_dirs:
                dest_path = target_dir / name
                if dest_path.exists() and dest_path.is_symlink():
                    dest_path.unlink()
                    console.print(f"[yellow]Disabled '{name}' in {adapter.name} ({scope})[/yellow]")
                elif dest_path.exists():
                    console.print(f"[yellow]Warning: '{dest_path}' is not a symlink. Skipping deletion.[/yellow]")
            
            update_config_state(ag, scope, f"{item_type}s", name, enable=False)

@cli.command()
def sync():
    """Hard override tool to rebuild project states from config.yaml."""
    console.print("[bold red]Warning: This will forcefully recreate symlinks based on config.yaml, potentially overwriting current manual configurations.[/bold red]")
    if not click.confirm("Are you sure you want to proceed?"):
        console.print("Sync aborted.")
        return
        
    config = load_config()
    for ag, scopes in config.get("agents", {}).items():
        if ag not in ADAPTERS:
            continue
            
        adapter = ADAPTERS[ag]
        for scope, item_types in scopes.items():
            is_glob = (scope == "global")
            for item_type_key, names in item_types.items():
                target_dirs = adapter.get_dir_paths(item_type_key, is_global=is_glob)
                opposite_dirs = adapter.get_opposite_dir_paths(item_type_key, is_global=is_glob)
                
                for name in names:
                    # Clean stale symlinks in opposite dirs
                    for opp_dir in opposite_dirs:
                        stale = opp_dir / name
                        if stale.exists() and stale.is_symlink():
                            stale.unlink()
                            
                    for target_dir in target_dirs:
                        src_path = AXON_DIR / item_type_key / name
                        dest_path = target_dir / name
                        
                        if dest_path.exists() and dest_path.is_symlink():
                            dest_path.unlink()
                        
                        if not dest_path.exists() and src_path.exists():
                            if not target_dir.exists():
                                target_dir.mkdir(parents=True, exist_ok=True)
                            os.symlink(src_path, dest_path)
                            
    console.print("[bold green]Sync complete.[/bold green]")

if __name__ == "__main__":
    cli()
