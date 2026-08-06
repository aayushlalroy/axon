"""
Axon CLI test suite.

All tests run in isolated tmp_path environments. The ~/.axon hub and any
agent target directories are patched via monkeypatch so nothing touches
the real filesystem.

Coverage goals:
  - agents, list, init, add commands
  - enable / disable for: skill (folder), principle (flat), workflow (flat)
  - per-agent skill_format edge cases (folder_skill_md / flat_mdc / flat_md / none)
  - global-fallback-to-local when agent has no global dirs
  - stale symlink cleanup when enabling in opposite category
  - sync command rebuilds all symlinks from config
  - Copilot (skill_format=none) is skipped for skills
  - Windsurf (no global dirs) falls back to local
  - Auto-detection of item type from staging hub
  - Disabling with wrong explicit type shows warning and leaves symlink intact
  - Workflows can be enabled/disabled for agents that support them
  - add command stages skill as folder/SKILL.md regardless of source shape
"""

import pytest
from click.testing import CliRunner
from pathlib import Path

from axon.cli import cli
from axon.adapters import (
    AgentAdapter,
    ADAPTERS,
    SKILL_FORMAT_FOLDER,
    SKILL_FORMAT_FLAT_MDC,
    SKILL_FORMAT_FLAT_MD,
    SKILL_FORMAT_NONE,
)


@pytest.fixture
def runner():
    return CliRunner()


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _make_staged_skill(axon_dir: Path, name: str, content: str = "skill body") -> Path:
    """Create a properly-staged skill folder: ~/.axon/skills/<name>/SKILL.md"""
    folder = axon_dir / "skills" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(content)
    return folder


def _make_staged_principle(axon_dir: Path, name: str, content: str = "principle body") -> Path:
    """Create a staged principle file: ~/.axon/principles/<name>"""
    f = axon_dir / "principles" / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content)
    return f


def _make_staged_workflow(axon_dir: Path, name: str, content: str = "workflow body") -> Path:
    """Create a staged workflow file: ~/.axon/workflows/<name>"""
    f = axon_dir / "workflows" / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content)
    return f


def _patch_axon(monkeypatch, tmp_path):
    """Patch AXON_DIR and CONFIG_FILE to a tmp directory."""
    import axon.cli as cli_module
    import axon.core as core_module

    mock_axon = tmp_path / ".axon"
    mock_axon.mkdir(parents=True, exist_ok=True)
    (mock_axon / "skills").mkdir(exist_ok=True)
    (mock_axon / "principles").mkdir(exist_ok=True)
    (mock_axon / "workflows").mkdir(exist_ok=True)

    monkeypatch.setattr(cli_module, "AXON_DIR", mock_axon)
    monkeypatch.setattr(core_module, "AXON_DIR", mock_axon)
    monkeypatch.setattr(core_module, "CONFIG_FILE", mock_axon / "config.yaml")
    return mock_axon


# ─────────────────────────────────────────────────────────
# Basic smoke tests
# ─────────────────────────────────────────────────────────

def test_agents_command(runner):
    """All agents should appear in 'axon agents' output."""
    result = runner.invoke(cli, ["agents"])
    assert result.exit_code == 0
    for name in ("Cursor", "Claude Code", "Gemini/Antigravity", "Devin", "Codex", "Windsurf", "GitHub Copilot"):
        assert name in result.output


def test_agents_shows_skill_format(runner):
    """Each agent line should mention its skill format."""
    result = runner.invoke(cli, ["agents"])
    assert "folder/SKILL.md" in result.output   # folder agents
    assert ".mdc flat file" in result.output     # Cursor
    assert ".md flat file" in result.output      # Windsurf
    assert "no skills" in result.output          # Copilot


def test_list_all_empty(runner, tmp_path, monkeypatch):
    """'axon list --all' should work even with nothing staged."""
    _patch_axon(monkeypatch, tmp_path)
    result = runner.invoke(cli, ["list", "--all"])
    assert result.exit_code == 0
    assert "All Staged Items" in result.output


def test_list_all_shows_staged_items(runner, tmp_path, monkeypatch):
    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "fast-format")
    _make_staged_principle(mock_axon, "no-comments.md")
    _make_staged_workflow(mock_axon, "pr-review.md")

    result = runner.invoke(cli, ["list", "--all"])
    assert result.exit_code == 0
    assert "fast-format" in result.output
    assert "no-comments.md" in result.output
    assert "pr-review.md" in result.output


# ─────────────────────────────────────────────────────────
# Init / scaffolding
# ─────────────────────────────────────────────────────────

def test_init_claude(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["init", "--agent", "claude"])
    assert result.exit_code == 0
    assert (tmp_path / "CLAUDE.md").is_file()
    assert (tmp_path / ".claude" / "skills").is_dir()
    assert (tmp_path / ".claude" / "rules").is_dir()
    assert (tmp_path / ".claude" / "commands").is_dir()


def test_init_cursor(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["init", "--agent", "cursor"])
    assert result.exit_code == 0
    assert (tmp_path / ".cursorrules").is_file()
    assert (tmp_path / ".cursor" / "rules").is_dir()


def test_init_devin(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["init", "--agent", "devin"])
    assert result.exit_code == 0
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / ".devin" / "skills").is_dir()
    assert (tmp_path / ".devin" / "workflows").is_dir()
    assert (tmp_path / ".agents" / "skills").is_dir()


def test_init_windsurf(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["init", "--agent", "windsurf"])
    assert result.exit_code == 0
    assert (tmp_path / ".windsurfrules").is_file()
    assert (tmp_path / ".windsurf" / "rules").is_dir()
    assert (tmp_path / ".windsurf" / "workflows").is_dir()


def test_init_copilot(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["init", "--agent", "copilot"])
    assert result.exit_code == 0
    assert (tmp_path / ".github" / "copilot-instructions.md").is_file()
    assert (tmp_path / ".github" / "instructions").is_dir()


def test_init_unknown_agent_warns(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["init", "--agent", "unknownbot"])
    assert result.exit_code == 0
    assert "not supported" in result.output


# ─────────────────────────────────────────────────────────
# Add command
# ─────────────────────────────────────────────────────────

def test_add_skill_from_flat_md(runner, tmp_path, monkeypatch):
    """Adding a plain .md file as a skill should create a folder with SKILL.md."""
    mock_axon = _patch_axon(monkeypatch, tmp_path)
    import axon.core as core_module
    monkeypatch.setattr(core_module, "AXON_DIR", mock_axon)

    src = tmp_path / "my-skill.md"
    src.write_text("---\nname: my-skill\ndescription: test\n---\nbody")

    result = runner.invoke(cli, ["add", str(src), "--type", "skill"])
    assert result.exit_code == 0
    staged_folder = mock_axon / "skills" / "my-skill"
    assert staged_folder.is_dir()
    assert (staged_folder / "SKILL.md").is_file()


def test_add_skill_from_folder(runner, tmp_path, monkeypatch):
    """Adding a folder containing SKILL.md should copy the folder."""
    mock_axon = _patch_axon(monkeypatch, tmp_path)
    import axon.core as core_module
    monkeypatch.setattr(core_module, "AXON_DIR", mock_axon)

    src_dir = tmp_path / "awesome-skill"
    src_dir.mkdir()
    (src_dir / "SKILL.md").write_text("---\nname: awesome\n---\nbody")
    (src_dir / "scripts").mkdir()
    (src_dir / "scripts" / "run.sh").write_text("#!/bin/bash\necho hi")

    result = runner.invoke(cli, ["add", str(src_dir), "--type", "skill"])
    assert result.exit_code == 0
    staged_folder = mock_axon / "skills" / "awesome-skill"
    assert staged_folder.is_dir()
    assert (staged_folder / "SKILL.md").is_file()
    assert (staged_folder / "scripts" / "run.sh").is_file()


def test_add_principle(runner, tmp_path, monkeypatch):
    mock_axon = _patch_axon(monkeypatch, tmp_path)
    import axon.core as core_module
    monkeypatch.setattr(core_module, "AXON_DIR", mock_axon)

    src = tmp_path / "coding-style.md"
    src.write_text("Always write tests.")

    result = runner.invoke(cli, ["add", str(src), "--type", "principle"])
    assert result.exit_code == 0
    assert (mock_axon / "principles" / "coding-style.md").is_file()


def test_add_workflow(runner, tmp_path, monkeypatch):
    mock_axon = _patch_axon(monkeypatch, tmp_path)
    import axon.core as core_module
    monkeypatch.setattr(core_module, "AXON_DIR", mock_axon)

    src = tmp_path / "pr-review.md"
    src.write_text("Step 1: check tests. Step 2: review.")

    result = runner.invoke(cli, ["add", str(src), "--type", "workflow"])
    assert result.exit_code == 0
    assert (mock_axon / "workflows" / "pr-review.md").is_file()


# ─────────────────────────────────────────────────────────
# Enable — folder_skill_md agents (Gemini, Claude, Devin, Codex)
# ─────────────────────────────────────────────────────────

def _make_folder_skill_adapter(skills_dir, principles_dir=None, workflows_dir=None):
    return AgentAdapter(
        name="TestFolderAgent",
        skill_format=SKILL_FORMAT_FOLDER,
        local_skill_dirs=[skills_dir],
        local_principle_dirs=[principles_dir] if principles_dir else [],
        local_workflow_dirs=[workflows_dir] if workflows_dir else [],
    )


def test_enable_skill_folder_format_creates_folder_symlink(runner, tmp_path, monkeypatch):
    """For folder_skill_md agents, enable must symlink the whole skill folder."""
    import axon.cli as cli_module
    import axon.core as core_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "fast-format")

    skills_dir = tmp_path / "agent" / "skills"
    skills_dir.mkdir(parents=True)

    adapter = _make_folder_skill_adapter(skills_dir)
    monkeypatch.setattr(cli_module, "ADAPTERS", {"myagent": adapter})

    result = runner.invoke(cli, ["enable", "skill", "fast-format"])
    assert result.exit_code == 0

    link = skills_dir / "fast-format"
    assert link.is_symlink()
    assert link.is_dir()
    # The symlink should resolve to the staged folder
    assert (link / "SKILL.md").exists()


def test_enable_skill_folder_format_dest_name_has_no_extension(runner, tmp_path, monkeypatch):
    """For folder agents, dest name must be the bare skill name (no extension)."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "my-tool")

    skills_dir = tmp_path / "agent" / "skills"
    skills_dir.mkdir(parents=True)

    monkeypatch.setattr(cli_module, "ADAPTERS", {"myagent": _make_folder_skill_adapter(skills_dir)})

    runner.invoke(cli, ["enable", "skill", "my-tool"])

    # No .md or .mdc extension
    assert not (skills_dir / "my-tool.md").exists()
    assert not (skills_dir / "my-tool.mdc").exists()
    assert (skills_dir / "my-tool").is_symlink()


# ─────────────────────────────────────────────────────────
# Enable — flat_mdc agent (Cursor)
# ─────────────────────────────────────────────────────────

def _make_flat_mdc_adapter(rules_dir):
    return AgentAdapter(
        name="CursorTest",
        skill_format=SKILL_FORMAT_FLAT_MDC,
        local_skill_dirs=[rules_dir],
        local_principle_dirs=[rules_dir],
    )


def test_enable_skill_flat_mdc_creates_mdc_symlink(runner, tmp_path, monkeypatch):
    """For Cursor (flat_mdc), enable skill → symlink SKILL.md as <name>.mdc."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "debug-helper")

    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)

    monkeypatch.setattr(cli_module, "ADAPTERS", {"cursor": _make_flat_mdc_adapter(rules_dir)})

    result = runner.invoke(cli, ["enable", "skill", "debug-helper"])
    assert result.exit_code == 0

    link = rules_dir / "debug-helper.mdc"
    assert link.is_symlink()
    # Should point to SKILL.md inside the staged folder
    assert link.resolve().name == "SKILL.md"


def test_enable_principle_flat_mdc_creates_md_symlink(runner, tmp_path, monkeypatch):
    """For Cursor, principles are .md files in the rules dir."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_principle(mock_axon, "always-types.md")

    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)

    monkeypatch.setattr(cli_module, "ADAPTERS", {"cursor": _make_flat_mdc_adapter(rules_dir)})

    result = runner.invoke(cli, ["enable", "principle", "always-types.md"])
    assert result.exit_code == 0
    assert (rules_dir / "always-types.md").is_symlink()


# ─────────────────────────────────────────────────────────
# Enable — flat_md agent (Windsurf)
# ─────────────────────────────────────────────────────────

def _make_flat_md_adapter(rules_dir, workflows_dir=None):
    return AgentAdapter(
        name="WindsurfTest",
        skill_format=SKILL_FORMAT_FLAT_MD,
        local_skill_dirs=[rules_dir],
        local_principle_dirs=[rules_dir],
        local_workflow_dirs=[workflows_dir] if workflows_dir else [],
    )


def test_enable_skill_flat_md_creates_md_symlink(runner, tmp_path, monkeypatch):
    """For Windsurf (flat_md), enable skill → symlink SKILL.md as <name>.md."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "my-rule")

    rules_dir = tmp_path / ".windsurf" / "rules"
    rules_dir.mkdir(parents=True)

    monkeypatch.setattr(cli_module, "ADAPTERS", {"windsurf": _make_flat_md_adapter(rules_dir)})

    result = runner.invoke(cli, ["enable", "skill", "my-rule"])
    assert result.exit_code == 0

    link = rules_dir / "my-rule.md"
    assert link.is_symlink()
    assert link.resolve().name == "SKILL.md"


# ─────────────────────────────────────────────────────────
# Enable — skill_format=none agent (Copilot)
# ─────────────────────────────────────────────────────────

def test_enable_skill_copilot_is_skipped(runner, tmp_path, monkeypatch):
    """Copilot has skill_format=none; enabling a skill should be skipped."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "some-skill")

    copilot_adapter = AgentAdapter(
        name="GitHubCopilot",
        skill_format=SKILL_FORMAT_NONE,
        local_skill_dirs=[],
        local_principle_dirs=[tmp_path / ".github" / "instructions"],
    )
    monkeypatch.setattr(cli_module, "ADAPTERS", {"copilot": copilot_adapter})

    result = runner.invoke(cli, ["enable", "skill", "some-skill"])
    assert result.exit_code == 0
    assert "does not support discrete skill files" in result.output


# ─────────────────────────────────────────────────────────
# Enable — workflows
# ─────────────────────────────────────────────────────────

def test_enable_workflow_creates_flat_md_symlink(runner, tmp_path, monkeypatch):
    """Workflows are flat files; enable should create a .md symlink in workflows dir."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_workflow(mock_axon, "pr-review.md")

    wf_dir = tmp_path / ".devin" / "workflows"
    wf_dir.mkdir(parents=True)

    adapter = AgentAdapter(
        name="DevinTest",
        skill_format=SKILL_FORMAT_FOLDER,
        local_workflow_dirs=[wf_dir],
    )
    monkeypatch.setattr(cli_module, "ADAPTERS", {"devin": adapter})

    result = runner.invoke(cli, ["enable", "workflow", "pr-review.md"])
    assert result.exit_code == 0
    assert (wf_dir / "pr-review.md").is_symlink()


def test_enable_workflow_skipped_for_agent_without_workflow_dirs(runner, tmp_path, monkeypatch):
    """Enable workflow for an agent with no workflow dirs should warn and skip."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_workflow(mock_axon, "deploy.md")

    adapter = AgentAdapter(
        name="NoWorkflow",
        skill_format=SKILL_FORMAT_FOLDER,
        local_workflow_dirs=[],  # no workflows
    )
    monkeypatch.setattr(cli_module, "ADAPTERS", {"nowf": adapter})

    result = runner.invoke(cli, ["enable", "workflow", "deploy.md"])
    assert result.exit_code == 0
    assert "does not have workflow directories" in result.output


# ─────────────────────────────────────────────────────────
# Enable — global fallback
# ─────────────────────────────────────────────────────────

def test_enable_global_falls_back_to_local_when_no_global_dirs(runner, tmp_path, monkeypatch):
    """When --global is requested but agent has no global dirs, fall back to local."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "my-skill")

    local_skills = tmp_path / "local" / "skills"
    local_skills.mkdir(parents=True)

    adapter = AgentAdapter(
        name="WindsurfTest",
        skill_format=SKILL_FORMAT_FLAT_MD,
        local_skill_dirs=[local_skills],
        global_skill_dirs=[],  # windsurf has no global
    )
    monkeypatch.setattr(cli_module, "ADAPTERS", {"windsurf": adapter})

    result = runner.invoke(cli, ["enable", "skill", "my-skill", "--global"])
    assert result.exit_code == 0
    assert "Falling back to local" in result.output
    # Should have created the link in local dir
    assert (local_skills / "my-skill.md").is_symlink()


# ─────────────────────────────────────────────────────────
# Enable / Disable — stale symlink cleanup
# ─────────────────────────────────────────────────────────

def test_enable_skill_removes_stale_principle_symlink(runner, tmp_path, monkeypatch):
    """If a stale symlink exists in the opposite dir, it should be cleaned up on enable."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    staged = _make_staged_skill(mock_axon, "tool")

    skills_dir = tmp_path / "agent" / "skills"
    principles_dir = tmp_path / "agent" / "principles"
    skills_dir.mkdir(parents=True)
    principles_dir.mkdir(parents=True)

    # Manually plant a stale symlink in principles dir (wrong location)
    stale = principles_dir / "tool"
    stale.symlink_to(staged)

    adapter = AgentAdapter(
        name="TestAgent",
        skill_format=SKILL_FORMAT_FOLDER,
        local_skill_dirs=[skills_dir],
        local_principle_dirs=[principles_dir],
    )
    monkeypatch.setattr(cli_module, "ADAPTERS", {"testagent": adapter})

    runner.invoke(cli, ["enable", "skill", "tool"])

    # Stale link in principles dir should be gone
    assert not stale.exists()
    # Correct link in skills dir should be present
    assert (skills_dir / "tool").is_symlink()


# ─────────────────────────────────────────────────────────
# Enable — auto-detection
# ─────────────────────────────────────────────────────────

def test_enable_auto_detects_skill(runner, tmp_path, monkeypatch):
    """Auto-detect 'skill' when no type prefix given and name is in skills staging."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "cool-skill")

    skills_dir = tmp_path / "agent" / "skills"
    skills_dir.mkdir(parents=True)

    monkeypatch.setattr(cli_module, "ADAPTERS", {"agent": _make_folder_skill_adapter(skills_dir)})

    result = runner.invoke(cli, ["enable", "cool-skill"])
    assert result.exit_code == 0
    assert (skills_dir / "cool-skill").is_symlink()


def test_enable_auto_detects_principle(runner, tmp_path, monkeypatch):
    """Auto-detect 'principle' when no type prefix given and name is in principles staging."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_principle(mock_axon, "style-guide.md")

    principles_dir = tmp_path / "agent" / "principles"
    principles_dir.mkdir(parents=True)

    adapter = AgentAdapter(
        name="TestAgent",
        skill_format=SKILL_FORMAT_FOLDER,
        local_principle_dirs=[principles_dir],
    )
    monkeypatch.setattr(cli_module, "ADAPTERS", {"agent": adapter})

    result = runner.invoke(cli, ["enable", "style-guide.md"])
    assert result.exit_code == 0
    assert (principles_dir / "style-guide.md").is_symlink()


def test_enable_unstaged_item_errors(runner, tmp_path, monkeypatch):
    """Enabling an item that doesn't exist in staging should print an error."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    monkeypatch.setattr(cli_module, "ADAPTERS", {})

    result = runner.invoke(cli, ["enable", "nonexistent-skill"])
    assert result.exit_code == 0
    assert "not staged" in result.output


# ─────────────────────────────────────────────────────────
# Disable
# ─────────────────────────────────────────────────────────

def test_disable_skill_removes_folder_symlink(runner, tmp_path, monkeypatch):
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    staged = _make_staged_skill(mock_axon, "my-skill")

    skills_dir = tmp_path / "agent" / "skills"
    skills_dir.mkdir(parents=True)
    link = skills_dir / "my-skill"
    link.symlink_to(staged)

    monkeypatch.setattr(cli_module, "ADAPTERS", {"agent": _make_folder_skill_adapter(skills_dir)})

    result = runner.invoke(cli, ["disable", "skill", "my-skill"])
    assert result.exit_code == 0
    assert not link.exists()


def test_disable_with_wrong_type_leaves_link_intact(runner, tmp_path, monkeypatch):
    """Disabling 'skill my-rule.md' when my-rule.md is a principle should warn."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_principle(mock_axon, "my-rule.md")

    rules_dir = tmp_path / "agent" / "rules"
    rules_dir.mkdir(parents=True)
    link = rules_dir / "my-rule.md"
    link.symlink_to(mock_axon / "principles" / "my-rule.md")

    adapter = AgentAdapter(
        name="TestAgent",
        skill_format=SKILL_FORMAT_FOLDER,
        local_skill_dirs=[],
        local_principle_dirs=[rules_dir],
    )
    monkeypatch.setattr(cli_module, "ADAPTERS", {"agent": adapter})

    result = runner.invoke(cli, ["disable", "skill", "my-rule.md"])
    assert result.exit_code == 0
    assert "Warning" in result.output
    # The principle symlink should remain intact
    assert link.is_symlink()


def test_disable_removes_all_variants(runner, tmp_path, monkeypatch):
    """Disable should clean up the correct extension variant."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "my-tool")

    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)

    # Simulate an already-enabled .mdc link
    staged_skill_md = mock_axon / "skills" / "my-tool" / "SKILL.md"
    link = rules_dir / "my-tool.mdc"
    link.symlink_to(staged_skill_md)

    adapter = _make_flat_mdc_adapter(rules_dir)
    monkeypatch.setattr(cli_module, "ADAPTERS", {"cursor": adapter})

    result = runner.invoke(cli, ["disable", "skill", "my-tool"])
    assert result.exit_code == 0
    assert not link.exists()


# ─────────────────────────────────────────────────────────
# Sync command
# ─────────────────────────────────────────────────────────

def test_sync_rebuilds_deleted_symlink(runner, tmp_path, monkeypatch):
    """Sync should recreate a deleted symlink based on config.yaml."""
    import axon.cli as cli_module
    import axon.core as core_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "the-skill")

    skills_dir = tmp_path / "agent" / "skills"
    skills_dir.mkdir(parents=True)

    adapter = _make_folder_skill_adapter(skills_dir)
    monkeypatch.setattr(cli_module, "ADAPTERS", {"agent": adapter})

    # Enable first to write config
    runner.invoke(cli, ["enable", "skill", "the-skill"])
    link = skills_dir / "the-skill"
    assert link.is_symlink()

    # Manually delete the symlink
    link.unlink()
    assert not link.exists()

    # Sync should restore it
    result = runner.invoke(cli, ["sync"], input="y\n")
    assert result.exit_code == 0
    assert link.is_symlink()
    assert (link / "SKILL.md").exists()


def test_sync_does_nothing_when_aborted(runner, tmp_path, monkeypatch):
    """If user says 'n' to sync confirmation, nothing should change."""
    import axon.cli as cli_module

    _patch_axon(monkeypatch, tmp_path)
    monkeypatch.setattr(cli_module, "ADAPTERS", {})

    result = runner.invoke(cli, ["sync"], input="n\n")
    assert result.exit_code == 0
    assert "aborted" in result.output.lower()


# ─────────────────────────────────────────────────────────
# Multi-agent routing (Devin's dual skill dirs)
# ─────────────────────────────────────────────────────────

def test_devin_enables_skill_in_both_dirs(runner, tmp_path, monkeypatch):
    """Devin has two skill dirs (.devin/skills and .agents/skills); both should get the link."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "deploy")

    monkeypatch.chdir(tmp_path)
    runner.invoke(cli, ["init", "--agent", "devin"])

    # Now enable for real devin adapter (uses current project dirs)
    result = runner.invoke(cli, ["enable", "skill", "deploy", "--agent", "devin"])
    assert result.exit_code == 0
    assert (tmp_path / ".devin" / "skills" / "deploy").is_symlink()
    assert (tmp_path / ".agents" / "skills" / "deploy").is_symlink()


def test_codex_enables_skill_in_codex_dir(runner, tmp_path, monkeypatch):
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "test-runner")

    monkeypatch.chdir(tmp_path)
    runner.invoke(cli, ["init", "--agent", "codex"])

    result = runner.invoke(cli, ["enable", "skill", "test-runner", "--agent", "codex"])
    assert result.exit_code == 0
    assert (tmp_path / ".codex" / "skills" / "test-runner").is_symlink()


def test_copilot_skips_skill_enable(runner, tmp_path, monkeypatch):
    """Copilot (skill_format=none) must skip when asked to enable a skill."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "my-skill")

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli, ["enable", "skill", "my-skill", "--agent", "copilot"])
    assert result.exit_code == 0
    assert "does not support discrete skill files" in result.output


def test_windsurf_uses_flat_md_for_skills(runner, tmp_path, monkeypatch):
    """Windsurf (flat_md) must place <name>.md symlink in .windsurf/rules."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "clean-code")

    monkeypatch.chdir(tmp_path)
    runner.invoke(cli, ["init", "--agent", "windsurf"])

    result = runner.invoke(cli, ["enable", "skill", "clean-code", "--agent", "windsurf"])
    assert result.exit_code == 0
    link = tmp_path / ".windsurf" / "rules" / "clean-code.md"
    assert link.is_symlink()
    # Must point to SKILL.md, not the whole folder
    assert link.resolve().name == "SKILL.md"


def test_cursor_uses_flat_mdc_for_skills(runner, tmp_path, monkeypatch):
    """Cursor (flat_mdc) must place <name>.mdc symlink in .cursor/rules."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "ts-rules")

    monkeypatch.chdir(tmp_path)
    runner.invoke(cli, ["init", "--agent", "cursor"])

    result = runner.invoke(cli, ["enable", "skill", "ts-rules", "--agent", "cursor"])
    assert result.exit_code == 0
    link = tmp_path / ".cursor" / "rules" / "ts-rules.mdc"
    assert link.is_symlink()
    assert link.resolve().name == "SKILL.md"


# ─────────────────────────────────────────────────────────
# List command (enabled items)
# ─────────────────────────────────────────────────────────

def test_list_shows_enabled_items_per_agent(runner, tmp_path, monkeypatch):
    """After enabling, 'axon list' should show the item under the correct agent."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "power-tool")

    skills_dir = tmp_path / "agent" / "skills"
    skills_dir.mkdir(parents=True)

    adapter = _make_folder_skill_adapter(skills_dir)
    monkeypatch.setattr(cli_module, "ADAPTERS", {"myagent": adapter})

    runner.invoke(cli, ["enable", "skill", "power-tool"])
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "power-tool" in result.output


def test_list_filter_by_agent(runner, tmp_path, monkeypatch):
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "a-skill")

    skills_dir = tmp_path / "agent" / "skills"
    skills_dir.mkdir(parents=True)
    adapter = _make_folder_skill_adapter(skills_dir)
    monkeypatch.setattr(cli_module, "ADAPTERS", {"agentA": adapter, "agentB": AgentAdapter("B")})

    runner.invoke(cli, ["enable", "skill", "a-skill", "--agent", "agentA"])
    result = runner.invoke(cli, ["list", "--agent", "agentA"])
    assert "a-skill" in result.output


# ─────────────────────────────────────────────────────────
# Edge case: enable re-uses existing broken symlink
# ─────────────────────────────────────────────────────────

def test_enable_replaces_broken_symlink(runner, tmp_path, monkeypatch):
    """If a broken symlink exists in the target dir, enable should replace it."""
    import axon.cli as cli_module

    mock_axon = _patch_axon(monkeypatch, tmp_path)
    _make_staged_skill(mock_axon, "relink-skill")

    skills_dir = tmp_path / "agent" / "skills"
    skills_dir.mkdir(parents=True)

    # Create a broken symlink
    broken = skills_dir / "relink-skill"
    broken.symlink_to("/nonexistent/path")
    assert broken.is_symlink()

    monkeypatch.setattr(cli_module, "ADAPTERS", {"agent": _make_folder_skill_adapter(skills_dir)})

    result = runner.invoke(cli, ["enable", "skill", "relink-skill"])
    assert result.exit_code == 0
    # Broken symlink should be replaced with a working one
    assert (skills_dir / "relink-skill").is_symlink()
    assert (skills_dir / "relink-skill" / "SKILL.md").exists()


# ─────────────────────────────────────────────────────────
# AgentAdapter unit tests
# ─────────────────────────────────────────────────────────

def test_adapter_uses_skill_folders_true_for_folder_format():
    adapter = AgentAdapter("X", skill_format=SKILL_FORMAT_FOLDER)
    assert adapter.uses_skill_folders is True


def test_adapter_uses_skill_folders_false_for_flat_formats():
    for fmt in (SKILL_FORMAT_FLAT_MDC, SKILL_FORMAT_FLAT_MD, SKILL_FORMAT_NONE):
        adapter = AgentAdapter("X", skill_format=fmt)
        assert adapter.uses_skill_folders is False


def test_adapter_supports_skills_false_for_none():
    adapter = AgentAdapter("X", skill_format=SKILL_FORMAT_NONE)
    assert adapter.supports_skills is False


def test_adapter_supports_skills_true_for_all_others():
    for fmt in (SKILL_FORMAT_FOLDER, SKILL_FORMAT_FLAT_MDC, SKILL_FORMAT_FLAT_MD):
        adapter = AgentAdapter("X", skill_format=fmt)
        assert adapter.supports_skills is True


def test_adapter_get_skill_suffix():
    assert AgentAdapter("X", skill_format=SKILL_FORMAT_FOLDER).get_skill_suffix() == ""
    assert AgentAdapter("X", skill_format=SKILL_FORMAT_FLAT_MDC).get_skill_suffix() == ".mdc"
    assert AgentAdapter("X", skill_format=SKILL_FORMAT_FLAT_MD).get_skill_suffix() == ".md"
    assert AgentAdapter("X", skill_format=SKILL_FORMAT_NONE).get_skill_suffix() == ""


def test_adapter_all_local_dirs_includes_workflows():
    p1 = Path("/a/skills")
    p2 = Path("/a/rules")
    p3 = Path("/a/workflows")
    adapter = AgentAdapter(
        "X",
        local_skill_dirs=[p1],
        local_principle_dirs=[p2],
        local_workflow_dirs=[p3],
    )
    assert p1 in adapter.all_local_dirs
    assert p2 in adapter.all_local_dirs
    assert p3 in adapter.all_local_dirs


def test_adapter_all_local_dirs_deduplicates():
    p = Path("/shared/rules")
    adapter = AgentAdapter(
        "X",
        local_skill_dirs=[p],
        local_principle_dirs=[p],  # same dir
    )
    assert adapter.all_local_dirs.count(p) == 1


def test_adapter_get_dir_paths_normalises_plural():
    p = Path("/skills")
    q = Path("/principles")
    adapter = AgentAdapter("X", local_skill_dirs=[p], local_principle_dirs=[q])
    assert adapter.get_dir_paths("skills") == [p]
    assert adapter.get_dir_paths("skill") == [p]
    assert adapter.get_dir_paths("principles") == [q]
    assert adapter.get_dir_paths("principle") == [q]


# ─────────────────────────────────────────────────────────
# Real ADAPTERS sanity checks (loaded from agents.yaml)
# ─────────────────────────────────────────────────────────

def test_real_adapters_loaded():
    assert len(ADAPTERS) >= 6


def test_devin_adapter_has_two_skill_dirs():
    adapter = ADAPTERS["devin"]
    assert len(adapter.local_skill_dirs) == 2


def test_cursor_adapter_uses_flat_mdc():
    assert ADAPTERS["cursor"].skill_format == SKILL_FORMAT_FLAT_MDC


def test_windsurf_adapter_uses_flat_md():
    assert ADAPTERS["windsurf"].skill_format == SKILL_FORMAT_FLAT_MD


def test_copilot_adapter_uses_none():
    assert ADAPTERS["copilot"].skill_format == SKILL_FORMAT_NONE


def test_folder_agents_use_folder_format():
    for key in ("claude", "gemini", "devin", "codex"):
        assert ADAPTERS[key].skill_format == SKILL_FORMAT_FOLDER, key


def test_windsurf_has_no_global_dirs():
    adapter = ADAPTERS["windsurf"]
    assert not adapter.global_skill_dirs
    assert not adapter.global_principle_dirs


def test_copilot_has_no_skill_dirs():
    adapter = ADAPTERS["copilot"]
    assert not adapter.local_skill_dirs
    assert not adapter.global_skill_dirs


def test_all_agents_have_name():
    for key, adapter in ADAPTERS.items():
        assert adapter.name, f"Agent '{key}' has no name"
