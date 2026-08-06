"""
test_adapters.py — Unit tests for axon.adapters

Tests:
  - agents.yaml is well-formed and loads without error
  - All 7 required agents are present
  - Each agent has a name and skill_format
  - Skill format values are all valid constants
  - Cursor: flat_mdc, has global dirs, no workflows
  - Claude: folder_skill_md, has global dirs, has workflows
  - Gemini: folder_skill_md, has global dirs, has workflows
  - Devin: folder_skill_md, has exactly 2 local skill dirs, has global dir
  - Codex: folder_skill_md, has global dir
  - Windsurf: flat_md, no global dirs at all
  - Copilot: none format, no skill dirs anywhere, no workflow dirs
  - AgentAdapter properties: uses_skill_folders, supports_skills, get_skill_suffix
  - AgentAdapter.get_dir_paths: returns correct dirs for skill/principle/workflow
  - AgentAdapter.get_dir_paths: handles plural form ("skills" vs "skill")
  - AgentAdapter.get_opposite_dir_paths: skill → principles, principle → skills
  - AgentAdapter.all_local_dirs: deduplicates shared dirs
  - AgentAdapter.all_local_dirs: includes workflow dirs
  - scaffold_local_env: creates dirs and touches files
  - scaffold_local_env: idempotent on repeated calls
  - scaffold_local_env: returns False for unknown agent
"""

import pytest
from pathlib import Path


# ─────────────────────────────────────────────────────────
# Constants import sanity check
# ─────────────────────────────────────────────────────────

def test_format_constants_defined():
    from axon.adapters import (
        SKILL_FORMAT_FOLDER, SKILL_FORMAT_FLAT_MDC,
        SKILL_FORMAT_FLAT_MD, SKILL_FORMAT_NONE,
    )
    assert SKILL_FORMAT_FOLDER == "folder_skill_md"
    assert SKILL_FORMAT_FLAT_MDC == "flat_mdc"
    assert SKILL_FORMAT_FLAT_MD == "flat_md"
    assert SKILL_FORMAT_NONE == "none"


# ─────────────────────────────────────────────────────────
# ADAPTERS registry
# ─────────────────────────────────────────────────────────

def test_all_required_agents_present():
    from axon.adapters import ADAPTERS
    for key in ("cursor", "claude", "gemini", "devin", "codex", "windsurf", "copilot"):
        assert key in ADAPTERS, f"Missing agent: {key}"


def test_all_agents_have_non_empty_name():
    from axon.adapters import ADAPTERS
    for key, adapter in ADAPTERS.items():
        assert adapter.name, f"Agent '{key}' has empty name"


def test_all_agents_have_valid_skill_format():
    from axon.adapters import (
        ADAPTERS, SKILL_FORMAT_FOLDER, SKILL_FORMAT_FLAT_MDC,
        SKILL_FORMAT_FLAT_MD, SKILL_FORMAT_NONE,
    )
    valid = {SKILL_FORMAT_FOLDER, SKILL_FORMAT_FLAT_MDC, SKILL_FORMAT_FLAT_MD, SKILL_FORMAT_NONE}
    for key, adapter in ADAPTERS.items():
        assert adapter.skill_format in valid, f"Agent '{key}' has unknown skill_format: {adapter.skill_format}"


# ─────────────────────────────────────────────────────────
# Per-agent structure assertions
# ─────────────────────────────────────────────────────────

def test_cursor_config():
    from axon.adapters import ADAPTERS, SKILL_FORMAT_FLAT_MDC
    a = ADAPTERS["cursor"]
    assert a.skill_format == SKILL_FORMAT_FLAT_MDC
    assert len(a.local_skill_dirs) == 1
    assert str(a.local_skill_dirs[0]).endswith(".cursor/rules")
    assert len(a.global_skill_dirs) == 1    # ~/.cursor/rules
    assert a.local_workflow_dirs == []      # Cursor has no workflow dirs
    assert a.local_file_targets            # .cursorrules


def test_claude_config():
    from axon.adapters import ADAPTERS, SKILL_FORMAT_FOLDER
    a = ADAPTERS["claude"]
    assert a.skill_format == SKILL_FORMAT_FOLDER
    assert any("skills" in str(d) for d in a.local_skill_dirs)
    assert any("rules" in str(d) for d in a.local_principle_dirs)
    assert any("commands" in str(d) for d in a.local_workflow_dirs)
    assert a.global_skill_dirs             # ~/.claude/skills
    assert a.local_file_targets            # CLAUDE.md


def test_gemini_config():
    from axon.adapters import ADAPTERS, SKILL_FORMAT_FOLDER
    a = ADAPTERS["gemini"]
    assert a.skill_format == SKILL_FORMAT_FOLDER
    assert any("agents/skills" in str(d) for d in a.local_skill_dirs)
    assert any("agents/rules" in str(d) for d in a.local_principle_dirs)
    assert any("agents/workflows" in str(d) for d in a.local_workflow_dirs)
    assert a.global_skill_dirs             # ~/.gemini/config/skills


def test_devin_has_two_local_skill_dirs():
    from axon.adapters import ADAPTERS
    a = ADAPTERS["devin"]
    assert len(a.local_skill_dirs) == 2
    dir_strings = [str(d) for d in a.local_skill_dirs]
    assert any(".devin/skills" in s for s in dir_strings)
    assert any(".agents/skills" in s for s in dir_strings)


def test_devin_has_global_skills():
    from axon.adapters import ADAPTERS
    a = ADAPTERS["devin"]
    assert a.global_skill_dirs
    assert any("devin" in str(d) for d in a.global_skill_dirs)


def test_devin_has_workflow_dirs():
    from axon.adapters import ADAPTERS
    a = ADAPTERS["devin"]
    assert a.local_workflow_dirs
    assert any("workflows" in str(d) for d in a.local_workflow_dirs)


def test_codex_config():
    from axon.adapters import ADAPTERS, SKILL_FORMAT_FOLDER
    a = ADAPTERS["codex"]
    assert a.skill_format == SKILL_FORMAT_FOLDER
    assert any("codex/skills" in str(d) for d in a.local_skill_dirs)
    assert a.global_skill_dirs


def test_windsurf_uses_flat_md():
    from axon.adapters import ADAPTERS, SKILL_FORMAT_FLAT_MD
    a = ADAPTERS["windsurf"]
    assert a.skill_format == SKILL_FORMAT_FLAT_MD


def test_windsurf_has_no_global_dirs():
    from axon.adapters import ADAPTERS
    a = ADAPTERS["windsurf"]
    assert not a.global_skill_dirs
    assert not a.global_principle_dirs
    assert not a.global_workflow_dirs


def test_windsurf_skills_and_principles_share_rules_dir():
    """Windsurf uses .windsurf/rules for both skills and principles."""
    from axon.adapters import ADAPTERS
    a = ADAPTERS["windsurf"]
    skill_dirs = [str(d) for d in a.local_skill_dirs]
    principle_dirs = [str(d) for d in a.local_principle_dirs]
    assert skill_dirs == principle_dirs


def test_copilot_has_no_skill_dirs():
    from axon.adapters import ADAPTERS, SKILL_FORMAT_NONE
    a = ADAPTERS["copilot"]
    assert a.skill_format == SKILL_FORMAT_NONE
    assert not a.local_skill_dirs
    assert not a.global_skill_dirs


def test_copilot_has_no_workflow_dirs():
    from axon.adapters import ADAPTERS
    a = ADAPTERS["copilot"]
    assert not a.local_workflow_dirs
    assert not a.global_workflow_dirs


def test_copilot_has_principle_dirs():
    from axon.adapters import ADAPTERS
    a = ADAPTERS["copilot"]
    assert a.local_principle_dirs
    assert any("instructions" in str(d) for d in a.local_principle_dirs)


def test_copilot_has_file_targets():
    from axon.adapters import ADAPTERS
    a = ADAPTERS["copilot"]
    assert a.local_file_targets
    assert any("copilot-instructions.md" in str(f) for f in a.local_file_targets)


# ─────────────────────────────────────────────────────────
# AgentAdapter property tests
# ─────────────────────────────────────────────────────────

def _make_adapter(skill_format, **kwargs):
    from axon.adapters import AgentAdapter
    return AgentAdapter("Test", skill_format=skill_format, **kwargs)


def test_uses_skill_folders_true_for_folder_format():
    from axon.adapters import SKILL_FORMAT_FOLDER
    assert _make_adapter(SKILL_FORMAT_FOLDER).uses_skill_folders is True


def test_uses_skill_folders_false_for_all_other_formats():
    from axon.adapters import SKILL_FORMAT_FLAT_MDC, SKILL_FORMAT_FLAT_MD, SKILL_FORMAT_NONE
    for fmt in (SKILL_FORMAT_FLAT_MDC, SKILL_FORMAT_FLAT_MD, SKILL_FORMAT_NONE):
        assert _make_adapter(fmt).uses_skill_folders is False, fmt


def test_supports_skills_false_for_none():
    from axon.adapters import SKILL_FORMAT_NONE
    assert _make_adapter(SKILL_FORMAT_NONE).supports_skills is False


def test_supports_skills_true_for_others():
    from axon.adapters import SKILL_FORMAT_FOLDER, SKILL_FORMAT_FLAT_MDC, SKILL_FORMAT_FLAT_MD
    for fmt in (SKILL_FORMAT_FOLDER, SKILL_FORMAT_FLAT_MDC, SKILL_FORMAT_FLAT_MD):
        assert _make_adapter(fmt).supports_skills is True, fmt


def test_get_skill_suffix_folder():
    from axon.adapters import SKILL_FORMAT_FOLDER
    assert _make_adapter(SKILL_FORMAT_FOLDER).get_skill_suffix() == ""


def test_get_skill_suffix_mdc():
    from axon.adapters import SKILL_FORMAT_FLAT_MDC
    assert _make_adapter(SKILL_FORMAT_FLAT_MDC).get_skill_suffix() == ".mdc"


def test_get_skill_suffix_md():
    from axon.adapters import SKILL_FORMAT_FLAT_MD
    assert _make_adapter(SKILL_FORMAT_FLAT_MD).get_skill_suffix() == ".md"


def test_get_skill_suffix_none():
    from axon.adapters import SKILL_FORMAT_NONE
    assert _make_adapter(SKILL_FORMAT_NONE).get_skill_suffix() == ""


# ─────────────────────────────────────────────────────────
# AgentAdapter.get_dir_paths
# ─────────────────────────────────────────────────────────

def test_get_dir_paths_skill_local():
    from axon.adapters import AgentAdapter, SKILL_FORMAT_FOLDER
    p = Path("/a/skills")
    a = AgentAdapter("X", skill_format=SKILL_FORMAT_FOLDER, local_skill_dirs=[p])
    assert a.get_dir_paths("skill", is_global=False) == [p]


def test_get_dir_paths_accepts_plural():
    from axon.adapters import AgentAdapter, SKILL_FORMAT_FOLDER
    p = Path("/a/skills")
    a = AgentAdapter("X", skill_format=SKILL_FORMAT_FOLDER, local_skill_dirs=[p])
    assert a.get_dir_paths("skills", is_global=False) == [p]


def test_get_dir_paths_principle():
    from axon.adapters import AgentAdapter
    p = Path("/a/rules")
    a = AgentAdapter("X", local_principle_dirs=[p])
    assert a.get_dir_paths("principle", is_global=False) == [p]


def test_get_dir_paths_workflow():
    from axon.adapters import AgentAdapter
    p = Path("/a/workflows")
    a = AgentAdapter("X", local_workflow_dirs=[p])
    assert a.get_dir_paths("workflow", is_global=False) == [p]


def test_get_dir_paths_global():
    from axon.adapters import AgentAdapter, SKILL_FORMAT_FOLDER
    p_local = Path("/local/skills")
    p_global = Path("/global/skills")
    a = AgentAdapter("X", skill_format=SKILL_FORMAT_FOLDER,
                     local_skill_dirs=[p_local], global_skill_dirs=[p_global])
    assert a.get_dir_paths("skill", is_global=True) == [p_global]
    assert a.get_dir_paths("skill", is_global=False) == [p_local]


# ─────────────────────────────────────────────────────────
# AgentAdapter.get_opposite_dir_paths
# ─────────────────────────────────────────────────────────

def test_get_opposite_dir_paths_skill_returns_principles():
    from axon.adapters import AgentAdapter
    skill_dir = Path("/skills")
    principle_dir = Path("/principles")
    a = AgentAdapter("X", local_skill_dirs=[skill_dir], local_principle_dirs=[principle_dir])
    assert principle_dir in a.get_opposite_dir_paths("skill", is_global=False)


def test_get_opposite_dir_paths_principle_returns_skills():
    from axon.adapters import AgentAdapter
    skill_dir = Path("/skills")
    principle_dir = Path("/principles")
    a = AgentAdapter("X", local_skill_dirs=[skill_dir], local_principle_dirs=[principle_dir])
    assert skill_dir in a.get_opposite_dir_paths("principle", is_global=False)


# ─────────────────────────────────────────────────────────
# AgentAdapter.all_local_dirs
# ─────────────────────────────────────────────────────────

def test_all_local_dirs_includes_all_types():
    from axon.adapters import AgentAdapter
    s = Path("/skills")
    p = Path("/principles")
    w = Path("/workflows")
    a = AgentAdapter("X", local_skill_dirs=[s], local_principle_dirs=[p], local_workflow_dirs=[w])
    assert s in a.all_local_dirs
    assert p in a.all_local_dirs
    assert w in a.all_local_dirs


def test_all_local_dirs_deduplicates_shared_dirs():
    from axon.adapters import AgentAdapter
    shared = Path("/rules")
    a = AgentAdapter("X", local_skill_dirs=[shared], local_principle_dirs=[shared])
    assert a.all_local_dirs.count(shared) == 1


# ─────────────────────────────────────────────────────────
# scaffold_local_env
# ─────────────────────────────────────────────────────────

def test_scaffold_creates_dirs_and_files(tmp_path, monkeypatch):
    from axon.adapters import ADAPTERS, scaffold_local_env, AgentAdapter, SKILL_FORMAT_FOLDER

    skills_dir = tmp_path / ".test-agent" / "skills"
    rules_dir = tmp_path / ".test-agent" / "rules"
    instruction_file = tmp_path / "TEST.md"

    test_adapter = AgentAdapter(
        "TestAgent",
        skill_format=SKILL_FORMAT_FOLDER,
        local_skill_dirs=[skills_dir],
        local_principle_dirs=[rules_dir],
        local_file_targets=[instruction_file],
    )
    monkeypatch.setitem(ADAPTERS, "testagent", test_adapter)
    monkeypatch.chdir(tmp_path)

    result = scaffold_local_env("testagent")
    assert result is True
    assert skills_dir.is_dir()
    assert rules_dir.is_dir()
    assert instruction_file.is_file()


def test_scaffold_is_idempotent(tmp_path, monkeypatch):
    from axon.adapters import ADAPTERS, scaffold_local_env, AgentAdapter, SKILL_FORMAT_FOLDER

    skills_dir = tmp_path / ".agent" / "skills"
    test_adapter = AgentAdapter("TestAgent", skill_format=SKILL_FORMAT_FOLDER,
                                local_skill_dirs=[skills_dir])
    monkeypatch.setitem(ADAPTERS, "testagent2", test_adapter)
    monkeypatch.chdir(tmp_path)

    scaffold_local_env("testagent2")
    scaffold_local_env("testagent2")  # second call must not raise
    assert skills_dir.is_dir()


def test_scaffold_returns_false_for_unknown_agent():
    from axon.adapters import scaffold_local_env
    assert scaffold_local_env("does-not-exist") is False


def test_scaffold_does_not_overwrite_existing_files(tmp_path, monkeypatch):
    from axon.adapters import ADAPTERS, scaffold_local_env, AgentAdapter

    f = tmp_path / "IMPORTANT.md"
    f.write_text("keep this content")

    test_adapter = AgentAdapter("X", local_file_targets=[f])
    monkeypatch.setitem(ADAPTERS, "keeper", test_adapter)
    monkeypatch.chdir(tmp_path)

    scaffold_local_env("keeper")
    assert f.read_text() == "keep this content"
