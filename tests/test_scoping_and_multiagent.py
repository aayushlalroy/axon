"""
Exhaustive test suite for Agent Scoping, Multi-Agent Flags, Idempotent Init,
and `enabled_agents` configuration in Axon CLI.
"""

import pytest
from click.testing import CliRunner
from pathlib import Path
import yaml

from axon.cli import cli
from axon.core import AXON_DIR, load_config
import axon.core
import axon.adapters


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Set up isolated ~/.axon hub and working project directory."""
    axon_dir = tmp_path / ".axon"
    axon_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(axon.core, "AXON_DIR", axon_dir)
    monkeypatch.setattr(axon.cli, "AXON_DIR", axon_dir)

    project_dir = tmp_path / "my-project"
    project_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(project_dir)

    # Mock home directory
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Patch ADAPTERS paths to point to project_dir for local dirs
    patched_adapters = {}
    for key, adapter in axon.adapters.ADAPTERS.items():
        new_adapter = axon.adapters.AgentAdapter(
            name=adapter.name,
            skill_format=adapter.skill_format,
            local_skill_dirs=[project_dir / p.relative_to(p.anchor) if p.is_absolute() else project_dir / p for p in adapter.local_skill_dirs],
            local_principle_dirs=[project_dir / p.relative_to(p.anchor) if p.is_absolute() else project_dir / p for p in adapter.local_principle_dirs],
            local_workflow_dirs=[project_dir / p.relative_to(p.anchor) if p.is_absolute() else project_dir / p for p in adapter.local_workflow_dirs],
            global_skill_dirs=adapter.global_skill_dirs,
            global_principle_dirs=adapter.global_principle_dirs,
            global_workflow_dirs=adapter.global_workflow_dirs,
            local_file_targets=[project_dir / p.relative_to(p.anchor) if p.is_absolute() else project_dir / p for p in adapter.local_file_targets],
            global_file_targets=adapter.global_file_targets,
            supports_compile=adapter.supports_compile,
        )
        patched_adapters[key] = new_adapter

    monkeypatch.setattr(axon.adapters, "ADAPTERS", patched_adapters)
    monkeypatch.setattr(axon.cli, "ADAPTERS", patched_adapters)

    return {"axon_dir": axon_dir, "project_dir": project_dir}


def _make_staged_skill(axon_dir: Path, name: str, content: str = "skill body") -> Path:
    folder = axon_dir / "skills" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(content)
    return folder


def _make_staged_principle(axon_dir: Path, name: str, content: str = "principle body") -> Path:
    f = axon_dir / "principles" / f"{name}.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content)
    return f


# ─────────────────────────────────────────────────────────
# 1. Init Scoping & Idempotence
# ─────────────────────────────────────────────────────────

def test_init_single_agent_only_creates_single_agent_dirs(runner, env):
    """axon init --agent cursor should only create .cursor/rules and leave other agent dirs uncreated."""
    res = runner.invoke(cli, ["init", "--agent", "cursor"])
    assert res.exit_code == 0

    project = env["project_dir"]
    assert (project / ".cursor" / "rules").exists()
    assert not (project / ".claude").exists()
    assert not (project / ".devin").exists()
    assert not (project / ".agents").exists()
    assert not (project / ".windsurf").exists()


def test_init_is_idempotent(runner, env):
    """Running axon init --agent cursor twice should succeed gracefully without overwriting or failing."""
    res1 = runner.invoke(cli, ["init", "--agent", "cursor"])
    assert res1.exit_code == 0

    res2 = runner.invoke(cli, ["init", "--agent", "cursor"])
    assert res2.exit_code == 0
    assert "already present" in res2.output.lower() or "skipping" in res2.output.lower() or "complete" in res2.output.lower()


def test_init_multiple_agent_flags(runner, env):
    """axon init --agent cursor --agent devin should initialize both cursor and devin but not others."""
    res = runner.invoke(cli, ["init", "--agent", "cursor", "--agent", "devin"])
    assert res.exit_code == 0

    project = env["project_dir"]
    assert (project / ".cursor" / "rules").exists()
    assert (project / ".devin" / "skills").exists()
    assert not (project / ".claude").exists()
    assert not (project / ".windsurf").exists()


def test_init_comma_separated_agents(runner, env):
    """axon init --agent cursor,devin should support comma-separated agent lists."""
    res = runner.invoke(cli, ["init", "--agent", "cursor,devin"])
    assert res.exit_code == 0

    project = env["project_dir"]
    assert (project / ".cursor" / "rules").exists()
    assert (project / ".devin" / "skills").exists()
    assert not (project / ".claude").exists()


def test_init_equals_flag_syntax(runner, env):
    """axon init --agent=cursor --agent=devin should support --agent=val syntax."""
    res = runner.invoke(cli, ["init", "--agent=cursor", "--agent=devin"])
    assert res.exit_code == 0

    project = env["project_dir"]
    assert (project / ".cursor" / "rules").exists()
    assert (project / ".devin" / "skills").exists()


def test_init_respects_enabled_agents_config(runner, env):
    """When axon init is called without --agent, it should read enabled_agents from ~/.axon/config.yaml."""
    cfg_file = env["axon_dir"] / "config.yaml"
    cfg = {"enabled_agents": ["gemini", "cursor"]}
    cfg_file.write_text(yaml.dump(cfg))

    res = runner.invoke(cli, ["init"])
    assert res.exit_code == 0

    project = env["project_dir"]
    assert (project / ".cursor" / "rules").exists()
    assert (project / ".agents" / "skills").exists()
    assert not (project / ".claude").exists()
    assert not (project / ".devin").exists()
    assert not (project / ".windsurf").exists()


# ─────────────────────────────────────────────────────────
# 2. Command Scoping (enable, disable, activate, deactivate, list, sync)
# ─────────────────────────────────────────────────────────

def test_enable_only_targets_initialized_project_agents(runner, env):
    """
    If project was initialized ONLY for cursor, running 'axon enable skill my-skill'
    without --agent must ONLY create symlinks in .cursor/rules and MUST NOT create .claude, .devin, etc.
    """
    _make_staged_skill(env["axon_dir"], "my-skill")

    # Init cursor ONLY
    runner.invoke(cli, ["init", "--agent", "cursor"])

    # Enable skill without --agent flag
    res = runner.invoke(cli, ["enable", "skill", "my-skill"])
    assert res.exit_code == 0

    project = env["project_dir"]
    assert (project / ".cursor" / "rules" / "my-skill.mdc").exists()
    assert not (project / ".claude").exists()
    assert not (project / ".devin").exists()
    assert not (project / ".agents").exists()
    assert not (project / ".windsurf").exists()


def test_disable_only_targets_initialized_project_agents(runner, env):
    """Disabling an item should only target initialized project agent dirs."""
    _make_staged_skill(env["axon_dir"], "my-skill")
    runner.invoke(cli, ["init", "--agent", "cursor"])
    runner.invoke(cli, ["enable", "skill", "my-skill"])

    res = runner.invoke(cli, ["disable", "skill", "my-skill"])
    assert res.exit_code == 0

    project = env["project_dir"]
    assert not (project / ".cursor" / "rules" / "my-skill.mdc").exists()
    assert not (project / ".claude").exists()


def test_explicit_agent_flag_warns_if_agent_not_initialized(runner, env):
    """
    If user passes --agent windsurf explicitly on enable, but windsurf is not initialized
    in project, axon should warn that windsurf is not initialized.
    """
    _make_staged_skill(env["axon_dir"], "my-skill")
    runner.invoke(cli, ["init", "--agent", "cursor"])

    res = runner.invoke(cli, ["enable", "skill", "my-skill", "--agent", "windsurf"])
    assert res.exit_code == 0
    assert "not initialized" in res.output.lower() or "warning" in res.output.lower() or "run 'axon init" in res.output.lower()


def test_explicit_multiple_agent_flags_on_enable(runner, env):
    """axon enable skill my-skill --agent cursor --agent devin should enable both."""
    _make_staged_skill(env["axon_dir"], "my-skill")
    runner.invoke(cli, ["init", "--agent", "cursor", "--agent", "devin"])

    res = runner.invoke(cli, ["enable", "skill", "my-skill", "--agent", "cursor", "--agent", "devin"])
    assert res.exit_code == 0

    project = env["project_dir"]
    assert (project / ".cursor" / "rules" / "my-skill.mdc").exists()
    assert (project / ".devin" / "skills" / "my-skill" / "SKILL.md").exists()
    assert not (project / ".claude").exists()


def test_activate_and_deactivate_scope(runner, env):
    """axon activate should operate on initialized project agents."""
    _make_staged_skill(env["axon_dir"], "my-skill")
    runner.invoke(cli, ["init", "--agent", "cursor"])

    res = runner.invoke(cli, ["activate", "skill", "my-skill"])
    assert res.exit_code == 0

    project = env["project_dir"]
    assert (project / ".cursor" / "rules" / "my-skill.mdc").exists()
    assert not (project / ".devin").exists()

    res_deact = runner.invoke(cli, ["deactivate", "skill", "my-skill"])
    assert res_deact.exit_code == 0


def test_sync_only_resets_initialized_project_agents(runner, env):
    """axon sync should only rebuild symlinks for initialized project agents."""
    _make_staged_skill(env["axon_dir"], "my-skill")
    runner.invoke(cli, ["init", "--agent", "cursor"])
    runner.invoke(cli, ["enable", "skill", "my-skill"])

    res = runner.invoke(cli, ["sync", "-y"])
    assert res.exit_code == 0

    project = env["project_dir"]
    assert (project / ".cursor" / "rules" / "my-skill.mdc").exists()
    assert not (project / ".claude").exists()
    assert not (project / ".devin").exists()
