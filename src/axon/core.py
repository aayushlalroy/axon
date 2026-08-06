import os
import yaml
from pathlib import Path
from rich.console import Console

console = Console()
AXON_DIR = Path(os.path.expanduser("~/.axon"))
CONFIG_FILE = AXON_DIR / "config.yaml"

def init_axon_dir():
    """Ensure ~/.axon structure exists."""
    AXON_DIR.mkdir(parents=True, exist_ok=True)
    (AXON_DIR / "skills").mkdir(exist_ok=True)
    (AXON_DIR / "principles").mkdir(exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w") as f:
            yaml.dump({"skills": {}, "principles": {}}, f)

def load_config():
    init_axon_dir()
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {"skills": {}, "principles": {}}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

def update_config_state(agent_name, scope, item_type, item_name, enable=True):
    config = load_config()
    if "agents" not in config:
        config["agents"] = {}
    if agent_name not in config["agents"]:
        config["agents"][agent_name] = {}
    if scope not in config["agents"][agent_name]:
        config["agents"][agent_name][scope] = {}
    
    # item_type is 'skills' or 'principles'
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
    skills = [f.name for f in (AXON_DIR / "skills").glob("*") if f.name != ".DS_Store"]
    principles = [f.name for f in (AXON_DIR / "principles").glob("*") if f.name != ".DS_Store"]
    return {"skills": skills, "principles": principles}
