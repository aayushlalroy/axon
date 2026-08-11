"""
Exhaustive test suite for symlink vs. physical copy override behavior across:
  - axon enable
  - axon activate (--local / --global)
  - axon deactivate (--local / --global)
  - axon disable
"""

import pytest
from pathlib import Path
from click.testing import CliRunner

from axon.cli import cli
import axon.core as core
import axon.cli as cli_module


@pytest.fixture
def runner():
    return CliRunner()


def _patch_axon(monkeypatch, tmp_path):
    mock_axon = tmp_path / ".axon"
    monkeypatch.setattr(core, "AXON_DIR", mock_axon)
    monkeypatch.setattr(core, "CONFIG_FILE", mock_axon / "config.yaml")
    monkeypatch.setattr(cli_module, "AXON_DIR", mock_axon)

    mock_axon.mkdir(parents=True, exist_ok=True)
    (mock_axon / "skills").mkdir(exist_ok=True)
    (mock_axon / "principles").mkdir(exist_ok=True)
    (mock_axon / "workflows").mkdir(exist_ok=True)
    (mock_axon / "config.yaml").write_text("agents: {}\n")

    return mock_axon


def test_enable_creates_symlinks_for_folder_skills(runner, monkeypatch, tmp_path):
    """axon enable must create a symlink for folder skill adapters (e.g. Gemini)."""
    mock_axon = _patch_axon(monkeypatch, tmp_path)

    # Stage skill
    skill_dir = mock_axon / "skills" / "test-folder-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: test-folder-skill\ndisable-model-invocation: false\n---\n# Folder Skill\n")

    project_dir = tmp_path / "project_folder"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    res = runner.invoke(cli, ["enable", "skill", "test-folder-skill", "--agent", "gemini"])
    assert res.exit_code == 0

    target = project_dir / ".agents" / "skills" / "test-folder-skill"
    assert target.exists()
    assert target.is_symlink(), "axon enable MUST create a symlink directory, not a physical copy!"
    assert target.resolve() == skill_dir.resolve()


def test_enable_creates_symlinks_for_flat_mdc_skills(runner, monkeypatch, tmp_path):
    """axon enable must create a symlink file for flat file adapters (e.g. Cursor)."""
    mock_axon = _patch_axon(monkeypatch, tmp_path)

    skill_dir = mock_axon / "skills" / "test-flat-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: test-flat-skill\ndisable-model-invocation: false\n---\n# Flat Skill\n")

    project_dir = tmp_path / "project_flat"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    res = runner.invoke(cli, ["enable", "skill", "test-flat-skill", "--agent", "cursor"])
    assert res.exit_code == 0

    target = project_dir / ".cursor" / "rules" / "test-flat-skill.mdc"
    assert target.exists()
    assert target.is_symlink(), "axon enable MUST create a symlink file for flat-file adapters!"
    assert target.resolve() == (skill_dir / "SKILL.md").resolve()


def test_local_deactivate_divergence_creates_physical_override(runner, monkeypatch, tmp_path):
    """
    When local deactivate is called and base file in ~/.axon/ has disable-model-invocation: false:
    - Target MUST be converted from a symlink into a physical copy override.
    - Frontmatter on local target MUST be updated to disable-model-invocation: true.
    - Base file in ~/.axon/ MUST remain untouched (disable-model-invocation: false).
    """
    mock_axon = _patch_axon(monkeypatch, tmp_path)

    base_skill = mock_axon / "skills" / "override-skill"
    base_skill.mkdir(parents=True)
    base_file = base_skill / "SKILL.md"
    base_file.write_text("---\nname: override-skill\ndisable-model-invocation: false\n---\n# Override Skill\n")

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    # 1. Enable -> creates symlink
    runner.invoke(cli, ["enable", "skill", "override-skill", "--agent", "gemini"])
    target = project_dir / ".agents" / "skills" / "override-skill"
    assert target.is_symlink()

    # 2. Deactivate locally -> diverges from base file (false -> true)
    res = runner.invoke(cli, ["deactivate", "skill", "override-skill", "--local", "--agent", "gemini"])
    assert res.exit_code == 0
    assert "local override" in res.output

    assert target.exists()
    assert not target.is_symlink(), "Local divergence MUST convert symlink into a physical copy override!"
    assert core.get_auto_invocation_status(target) is False
    assert core.get_auto_invocation_status(base_skill) is True, "Base file in ~/.axon/ must NOT be modified by local toggle!"


def test_local_activate_convergence_reverts_to_symlink(runner, monkeypatch, tmp_path):
    """
    When local activate is called and base file in ~/.axon/ has disable-model-invocation: false:
    - Local state now matches base file.
    - Physical copy override MUST be removed and replaced with a SYMLINK.
    """
    mock_axon = _patch_axon(monkeypatch, tmp_path)

    base_skill = mock_axon / "skills" / "override-skill"
    base_skill.mkdir(parents=True)
    base_file = base_skill / "SKILL.md"
    base_file.write_text("---\nname: override-skill\ndisable-model-invocation: false\n---\n# Override Skill\n")

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    # 1. Enable & Deactivate locally (creates physical copy override)
    runner.invoke(cli, ["enable", "skill", "override-skill", "--agent", "gemini"])
    runner.invoke(cli, ["deactivate", "skill", "override-skill", "--local", "--agent", "gemini"])
    target = project_dir / ".agents" / "skills" / "override-skill"
    assert not target.is_symlink()

    # 2. Activate locally -> matches base file (false -> false)
    res = runner.invoke(cli, ["activate", "skill", "override-skill", "--local", "--agent", "gemini"])
    assert res.exit_code == 0
    assert "symlink" in res.output

    assert target.exists()
    assert target.is_symlink(), "Local convergence back to base file state MUST revert target back into a symlink!"
    assert core.get_auto_invocation_status(target) is True


def test_global_activate_modifies_base_file_and_preserves_symlinks(runner, monkeypatch, tmp_path):
    """
    When activate --global is called:
    - Base file in ~/.axon/ MUST be updated.
    - Symlinked targets MUST remain symlinks and inherit the updated status.
    """
    mock_axon = _patch_axon(monkeypatch, tmp_path)

    base_skill = mock_axon / "skills" / "global-skill"
    base_skill.mkdir(parents=True)
    base_file = base_skill / "SKILL.md"
    base_file.write_text("---\nname: global-skill\ndisable-model-invocation: true\n---\n# Global Skill\n")

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    runner.invoke(cli, ["enable", "skill", "global-skill", "--agent", "gemini"])
    target = project_dir / ".agents" / "skills" / "global-skill"
    assert target.is_symlink()
    assert core.get_auto_invocation_status(target) is False

    # Global activate
    res = runner.invoke(cli, ["activate", "skill", "global-skill", "--global", "--agent", "gemini"])
    assert res.exit_code == 0

    assert core.get_auto_invocation_status(base_skill) is True
    assert target.is_symlink(), "Global activate must preserve target as a symlink!"
    assert core.get_auto_invocation_status(target) is True


def test_deactivate_when_global_already_disabled_keeps_symlink(runner, monkeypatch, tmp_path):
    """
    If base file in ~/.axon/ already has disable-model-invocation: true,
    running local deactivate must keep/create a SYMLINK, NOT edit a physical file!
    """
    mock_axon = _patch_axon(monkeypatch, tmp_path)

    base_skill = mock_axon / "skills" / "already-disabled"
    base_skill.mkdir(parents=True)
    base_file = base_skill / "SKILL.md"
    base_file.write_text("---\nname: already-disabled\ndisable-model-invocation: true\n---\n# Disabled Skill\n")

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    # Enable -> symlink
    runner.invoke(cli, ["enable", "skill", "already-disabled", "--agent", "gemini"])
    target = project_dir / ".agents" / "skills" / "already-disabled"
    assert target.is_symlink()

    # Deactivate locally -> matches base file (both want disable-model-invocation: true)
    res = runner.invoke(cli, ["deactivate", "skill", "already-disabled", "--local", "--agent", "gemini"])
    assert res.exit_code == 0
    assert "symlink" in res.output

    assert target.exists()
    assert target.is_symlink(), "Local deactivate when global is already disabled MUST preserve/re-create symlink!"


def test_disable_removes_symlink_or_copy(runner, monkeypatch, tmp_path):
    """axon disable must cleanly remove symlinks and physical copies."""
    mock_axon = _patch_axon(monkeypatch, tmp_path)

    base_skill = mock_axon / "skills" / "del-skill"
    base_skill.mkdir(parents=True)
    (base_skill / "SKILL.md").write_text("---\nname: del-skill\n---\n# Del Skill\n")

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    # 1. Enable -> Symlink
    runner.invoke(cli, ["enable", "skill", "del-skill", "--agent", "gemini"])
    target = project_dir / ".agents" / "skills" / "del-skill"
    assert target.is_symlink()

    # 2. Disable -> removes symlink
    res = runner.invoke(cli, ["disable", "skill", "del-skill", "--agent", "gemini"])
    assert res.exit_code == 0
    assert not target.exists(), "axon disable MUST remove the symlink!"

    # 3. Enable + Deactivate locally (physical copy) + Disable -> removes physical copy
    runner.invoke(cli, ["enable", "skill", "del-skill", "--agent", "gemini"])
    runner.invoke(cli, ["deactivate", "skill", "del-skill", "--local", "--agent", "gemini"])
    assert not target.is_symlink()

    res_dis = runner.invoke(cli, ["disable", "skill", "del-skill", "--agent", "gemini"])
    assert res_dis.exit_code == 0
    assert not target.exists(), "axon disable MUST remove physical copy overrides!"


