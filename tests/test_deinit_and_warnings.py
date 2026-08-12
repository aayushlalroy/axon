"""
TDD test suite for 'axon deinit' command and actionable warning messages in Axon CLI.
"""

import pytest
from click.testing import CliRunner
from pathlib import Path

from axon.cli import cli
import axon.core
import axon.adapters


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def env(tmp_path, monkeypatch):
    axon_dir = tmp_path / ".axon"
    axon_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(axon.core, "AXON_DIR", axon_dir)
    monkeypatch.setattr(axon.cli, "AXON_DIR", axon_dir)

    project_dir = tmp_path / "my-project"
    project_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(project_dir)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

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


# ─────────────────────────────────────────────────────────
# 1. Actionable Warning Messages Tests
# ─────────────────────────────────────────────────────────

def test_unsupported_agent_warning_suggests_axon_agents(runner, env):
    """When an unsupported agent name like 'antigravity' or 'foo' is passed, warning suggests running 'axon agents' or using 'gemini'."""
    res = runner.invoke(cli, ["init", "--agent", "antigravity"])
    assert res.exit_code == 0
    assert "axon agents" in res.output.lower() or "gemini" in res.output.lower()


def test_uninitialized_agent_warning_suggests_axon_init(runner, env):
    """When an uninitialized agent is passed to enable, warning suggests running 'axon init --agent <name>'."""
    runner.invoke(cli, ["init", "--agent", "cursor"])
    res = runner.invoke(cli, ["enable", "some-skill", "--agent", "windsurf"])
    assert res.exit_code == 0
    assert "axon init" in res.output.lower() or "axon agents" in res.output.lower()


# ─────────────────────────────────────────────────────────
# 2. De-initialize (axon deinit) Tests
# ─────────────────────────────────────────────────────────

def test_deinit_single_agent(runner, env):
    """axon deinit --agent cursor -y should remove cursor directories and files in project."""
    runner.invoke(cli, ["init", "--agent", "cursor", "--agent", "devin"])
    project = env["project_dir"]
    assert (project / ".cursor" / "rules").exists()
    assert (project / ".devin" / "skills").exists()

    res = runner.invoke(cli, ["deinit", "--agent", "cursor", "-y"])
    assert res.exit_code == 0

    assert not (project / ".cursor").exists()
    assert not (project / ".cursorrules").exists()
    assert (project / ".devin" / "skills").exists()  # Devin untouched


def test_deinit_all_initialized_agents(runner, env):
    """axon deinit -y should remove all project agent directories and managed files."""
    runner.invoke(cli, ["init", "--agent", "cursor", "--agent", "devin"])
    project = env["project_dir"]

    res = runner.invoke(cli, ["deinit", "-y"])
    assert res.exit_code == 0
    assert "de-initialized" in res.output.lower() or "deinit" in res.output.lower() or "removed" in res.output.lower()

    assert not (project / ".cursor").exists()
    assert not (project / ".cursorrules").exists()
    assert not (project / ".devin").exists()
    assert not (project / "AGENTS.md").exists()


def test_deinit_requires_confirmation_unless_yes(runner, env):
    """axon deinit should prompt for confirmation unless -y is passed."""
    runner.invoke(cli, ["init", "--agent", "cursor"])
    project = env["project_dir"]

    # Cancel confirmation
    res_cancel = runner.invoke(cli, ["deinit"], input="n\n")
    assert res_cancel.exit_code == 0
    assert (project / ".cursor").exists()

    # Accept confirmation
    res_confirm = runner.invoke(cli, ["deinit"], input="y\n")
    assert res_confirm.exit_code == 0
    assert not (project / ".cursor").exists()
