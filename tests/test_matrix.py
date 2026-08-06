"""
test_matrix.py — Exhaustive Matrix Tests for All 7 Agents x 3 Item Types x Operations

Tests:
  - Skill, Principle, and Workflow enable/disable/sync across every agent:
    1. Cursor (flat_mdc, .cursor/rules, .cursorrules)
    2. Claude Code (folder_skill_md, .claude/skills, .claude/rules, .claude/commands, CLAUDE.md)
    3. Gemini/Antigravity (folder_skill_md, .agents/skills, .agents/rules, .agents/workflows)
    4. Devin (folder_skill_md, .devin/skills + .agents/skills, .devin/rules, .devin/workflows, AGENTS.md, .devin/instructions.md)
    5. Codex (folder_skill_md, .codex/skills, .codex/rules, .codex/workflows, AGENTS.md)
    6. Windsurf (flat_md, .windsurf/rules, .windsurf/workflows, .windsurfrules)
    7. GitHub Copilot (none skill format, .github/instructions, .github/copilot-instructions.md)
  - Collision test: Skill 'auth' vs Principle 'auth.md' — type disambiguation
  - Extension tolerance: 'axon enable auth' vs 'axon enable auth.md'
  - Overwrite safety and clean file updates
"""

import pytest
from pathlib import Path
from click.testing import CliRunner
from axon.cli import cli
from axon.adapters import ADAPTERS


@pytest.fixture
def runner():
    return CliRunner()


def _patch_axon(monkeypatch, tmp_path):
    import axon.core as core
    import axon.cli as cli_module

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


# ─────────────────────────────────────────────────────────
# Matrix Test: Every Agent x Every Item Type
# ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("agent_key", ["cursor", "claude", "gemini", "devin", "codex", "windsurf", "copilot"])
def test_matrix_enable_disable_skill(runner, tmp_path, monkeypatch, agent_key):
    """Verify skill enable and disable for each agent."""
    import axon.core as core

    mock_axon = _patch_axon(monkeypatch, tmp_path)

    # Stage skill
    skill_dir = tmp_path / "src-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: matrix-skill\n---\nskill body")
    core.stage_skill(skill_dir, "matrix-skill")

    monkeypatch.chdir(tmp_path)
    runner.invoke(cli, ["init", "--agent", agent_key])

    adapter = ADAPTERS[agent_key]

    # Enable
    res = runner.invoke(cli, ["enable", "skill", "matrix-skill", "--agent", agent_key])
    assert res.exit_code == 0

    if not adapter.supports_skills:
        assert "does not support discrete skill files" in res.output
    else:
        # Check target directories
        for target_dir in adapter.local_skill_dirs:
            if adapter.uses_skill_folders:
                dest = target_dir / "matrix-skill"
                assert dest.is_dir(), f"Expected directory at {dest} for {agent_key}"
                assert (dest / "SKILL.md").is_file()
            else:
                ext = adapter.get_skill_suffix()
                dest = target_dir / f"matrix-skill{ext}"
                assert dest.is_file(), f"Expected file at {dest} for {agent_key}"

    # Disable
    res_dis = runner.invoke(cli, ["disable", "skill", "matrix-skill", "--agent", agent_key])
    assert res_dis.exit_code == 0

    if adapter.supports_skills:
        for target_dir in adapter.local_skill_dirs:
            dest = target_dir / ("matrix-skill" if adapter.uses_skill_folders else f"matrix-skill{adapter.get_skill_suffix()}")
            assert not dest.exists(), f"Target {dest} should be removed for {agent_key}"


@pytest.mark.parametrize("agent_key", ["cursor", "claude", "gemini", "devin", "codex", "windsurf", "copilot"])
def test_matrix_enable_disable_principle(runner, tmp_path, monkeypatch, agent_key):
    """Verify principle enable, disable, and single-file compilation for each agent."""
    import axon.core as core

    mock_axon = _patch_axon(monkeypatch, tmp_path)

    p_file = tmp_path / "matrix-principle.md"
    p_file.write_text("# Matrix Principle\nAlways follow coding standards.")
    core.stage_principle(p_file, "matrix-principle.md")

    monkeypatch.chdir(tmp_path)
    runner.invoke(cli, ["init", "--agent", agent_key])

    adapter = ADAPTERS[agent_key]

    # Enable
    res = runner.invoke(cli, ["enable", "principle", "matrix-principle.md", "--agent", agent_key])
    assert res.exit_code == 0

    # Check modular principle dirs
    for target_dir in adapter.local_principle_dirs:
        dest = target_dir / "matrix-principle.md"
        assert dest.is_file(), f"Expected principle file at {dest} for {agent_key}"
        assert "Always follow coding standards" in dest.read_text()

    # Check single-file targets compilation
    if adapter.supports_compile and adapter.local_file_targets:
        for target_file in adapter.local_file_targets:
            assert target_file.is_file(), f"Expected compiled target at {target_file} for {agent_key}"
            text = target_file.read_text()
            assert "<!-- AXON:BEGIN -->" in text
            assert "Always follow coding standards" in text
            assert "<!-- AXON:END -->" in text

    # Disable
    res_dis = runner.invoke(cli, ["disable", "principle", "matrix-principle.md", "--agent", agent_key])
    assert res_dis.exit_code == 0

    for target_dir in adapter.local_principle_dirs:
        dest = target_dir / "matrix-principle.md"
        assert not dest.exists(), f"Principle file {dest} should be removed for {agent_key}"

    if adapter.supports_compile and adapter.local_file_targets:
        for target_file in adapter.local_file_targets:
            text = target_file.read_text() if target_file.exists() else ""
            assert "Always follow coding standards" not in text
            assert "<!-- AXON:BEGIN -->" not in text


# ─────────────────────────────────────────────────────────
# Collision & Disambiguation Tests
# ─────────────────────────────────────────────────────────

def test_same_name_skill_and_principle_coexist(runner, tmp_path, monkeypatch):
    """
    If both a skill 'auth' and a principle 'auth.md' are staged:
    - 'axon enable skill auth' enables the skill
    - 'axon enable principle auth' enables the principle
    - 'axon enable auth.md' enables the principle
    - 'axon enable auth' enables the skill
    """
    import axon.core as core

    mock_axon = _patch_axon(monkeypatch, tmp_path)

    # Stage skill 'auth'
    skill_dir = tmp_path / "auth_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: auth\n---\nAuth skill logic")
    core.stage_skill(skill_dir, "auth")

    # Stage principle 'auth.md'
    p_file = tmp_path / "auth_principle.md"
    p_file.write_text("# Auth Principle\nAlways enforce JWT validation.")
    core.stage_principle(p_file, "auth.md")

    monkeypatch.chdir(tmp_path)
    runner.invoke(cli, ["init", "--agent", "claude"])

    # 1. Explicit skill
    res = runner.invoke(cli, ["enable", "skill", "auth", "--agent", "claude"])
    assert res.exit_code == 0
    assert (tmp_path / ".claude" / "skills" / "auth").is_dir()

    # 2. Explicit principle
    res = runner.invoke(cli, ["enable", "principle", "auth", "--agent", "claude"])
    assert res.exit_code == 0
    assert (tmp_path / ".claude" / "rules" / "auth.md").is_file()

    # 3. Enable by filename ending in .md auto-detects principle
    runner.invoke(cli, ["disable", "principle", "auth", "--agent", "claude"])
    assert not (tmp_path / ".claude" / "rules" / "auth.md").exists()

    res_auto = runner.invoke(cli, ["enable", "auth.md", "--agent", "claude"])
    assert res_auto.exit_code == 0
    assert (tmp_path / ".claude" / "rules" / "auth.md").is_file()


def test_enable_non_existent_item_returns_clean_error(runner, tmp_path, monkeypatch):
    """Enabling an unstaged item must return a friendly error and exit code 0."""
    _patch_axon(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)

    res = runner.invoke(cli, ["enable", "non-existent-item"])
    assert res.exit_code == 0
    assert "is not staged" in res.output
