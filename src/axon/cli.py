import click
import shutil
import os
from rich.console import Console
from pathlib import Path
from axon.adapters import ADAPTERS, scaffold_local_env
from axon.core import get_staged_items, load_config, AXON_DIR, update_config_state



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
    console.print("- Claude Code [dim](.clauderc)[/dim]")
    console.print("- Gemini/Antigravity [dim](~/.gemini/config/, .agents/)[/dim]")

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
        
        # Determine local vs global for this agent
        # For V1, we just print the state from config.yaml
        agent_config = config.get("agents", {}).get(ag, {})
        
        local_skills = agent_config.get("local", {}).get("skills", [])
        global_skills = agent_config.get("global", {}).get("skills", [])
        
        if not local_skills and not global_skills:
            console.print("  [dim]No items enabled.[/dim]")
            continue
            
        if local_skills:
            console.print("  [bold]Local:[/bold]")
            for s in local_skills:
                console.print(f"    - {s}")
        if global_skills:
            console.print("  [bold]Global:[/bold]")
            for s in global_skills:
                console.print(f"    - {s}")

@cli.command()
@click.argument('source_path', type=click.Path(exists=True))
@click.option('--name', help="Override the default name")
def add(source_path, name):
    """Launch interactive wizard to stage a new skill or principle."""
    src = Path(source_path)
    item_name = name if name else src.name
    
    console.print(f"[bold]Staging {src}[/bold]")
    item_type = click.prompt(
        "Is this a [1] Skill (On-Demand) or [2] Principle (Always On)?", 
        type=click.Choice(['1', '2'])
    )
    
    dest_dir = AXON_DIR / ("skills" if item_type == '1' else "principles")
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

@cli.command()
@click.argument('item_type', type=click.Choice(['skill', 'principle']))
@click.argument('names', nargs=-1, required=True)
@click.option('--global/--local', 'is_global', default=False, help="Enable globally or locally")
@click.option('--agent', help="Target specific agent (e.g. cursor)")
def enable(item_type, names, is_global, agent):
    """Enable one or more skills/principles."""
    staged = get_staged_items()
    valid_items = staged[f"{item_type}s"]
    
    agents_to_target = [agent] if agent else ADAPTERS.keys()
    
    for name in names:
        if name not in valid_items:
            console.print(f"[red]Error: '{name}' is not a staged {item_type}.[/red]")
            continue
            
        src_path = AXON_DIR / f"{item_type}s" / name
        
        for ag in agents_to_target:
            if ag not in ADAPTERS:
                continue
            adapter = ADAPTERS[ag]
            
            target_paths = adapter.get_paths(item_type, is_global=is_global)
            scope = "global" if is_global else "local"
            
            if is_global and not target_paths:
                console.print(f"[yellow]Warning: {adapter.name} does not support global file-based {item_type}s. Falling back to local.[/yellow]")
                target_paths = adapter.get_paths(item_type, is_global=False)
                scope = "local"
                
            for target_dir in target_paths:
                if target_dir.suffix: # Skip file compilation for now, handle symlinks only for skills/modular principles
                    continue
                
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
@click.argument('item_type', type=click.Choice(['skill', 'principle']))
@click.argument('names', nargs=-1, required=True)
@click.option('--global/--local', 'is_global', default=False, help="Disable globally or locally")
@click.option('--agent', help="Target specific agent (e.g. cursor)")
def disable(item_type, names, is_global, agent):
    """Disable one or more skills/principles."""
    agents_to_target = [agent] if agent else ADAPTERS.keys()
    
    for name in names:
        for ag in agents_to_target:
            if ag not in ADAPTERS:
                continue
            adapter = ADAPTERS[ag]
            
            target_paths = adapter.get_paths(item_type, is_global=is_global)
            scope = "global" if is_global else "local"
            
            if is_global and not target_paths:
                target_paths = adapter.get_paths(item_type, is_global=False)
                scope = "local"
                
            for target_dir in target_paths:
                if target_dir.suffix:
                    continue
                    
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
                target_paths = adapter.get_paths(item_type_key, is_global=is_glob)
                
                for target_dir in target_paths:
                    if target_dir.suffix:
                        continue
                    
                    for name in names:
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
