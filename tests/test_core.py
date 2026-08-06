"""
test_core.py — Unit tests for axon.core

Tests:
  - init_axon_dir: creates all required dirs and config file
  - init_axon_dir: idempotent on repeated calls
  - load_config: returns empty structure if missing
  - load_config: roundtrips YAML correctly
  - save_config / load_config roundtrip
  - update_config_state: enable adds item once (idempotent)
  - update_config_state: disable removes item
  - update_config_state: disable on absent item is a no-op
  - update_config_state: creates nested keys automatically
  - get_staged_items: lists skills (folders), principles, workflows
  - get_staged_items: skips .DS_Store entries
  - get_staged_items: returns empty lists when hub is missing
  - stage_skill: flat .md → folder/SKILL.md
  - stage_skill: existing folder with SKILL.md → copies as-is
  - stage_skill: existing folder without SKILL.md, single .md → renamed to SKILL.md
  - stage_skill: existing folder with multiple .md files → all kept, no rename
  - stage_skill: raises FileExistsError without overwrite=True
  - stage_skill: overwrites when overwrite=True
  - stage_principle: copies flat file
  - stage_principle: raises ValueError for directory source
  - stage_principle: raises FileExistsError without overwrite
  - stage_workflow: copies flat file
  - stage_workflow: raises ValueError for directory source
"""

import pytest
import yaml
from pathlib import Path


@pytest.fixture
def axon_home(tmp_path, monkeypatch):
    """Patch AXON_DIR and CONFIG_FILE to an isolated tmp dir."""
    import axon.core as core
    hub = tmp_path / ".axon"
    monkeypatch.setattr(core, "AXON_DIR", hub)
    monkeypatch.setattr(core, "CONFIG_FILE", hub / "config.yaml")
    return hub


# ─────────────────────────────────────────────────────────
# init_axon_dir
# ─────────────────────────────────────────────────────────

def test_init_axon_dir_creates_hub(axon_home):
    import axon.core as core
    core.init_axon_dir()
    assert axon_home.is_dir()
    assert (axon_home / "skills").is_dir()
    assert (axon_home / "principles").is_dir()
    assert (axon_home / "workflows").is_dir()
    assert (axon_home / "config.yaml").is_file()


def test_init_axon_dir_is_idempotent(axon_home):
    import axon.core as core
    core.init_axon_dir()
    core.init_axon_dir()   # second call must not raise
    assert (axon_home / "skills").is_dir()


def test_init_axon_dir_does_not_overwrite_existing_config(axon_home):
    import axon.core as core
    axon_home.mkdir(parents=True)
    cfg = axon_home / "config.yaml"
    cfg.write_text("agents:\n  cursor:\n    local:\n      skills: [my-skill]\n")
    core.init_axon_dir()
    # should preserve existing content
    assert "my-skill" in cfg.read_text()


# ─────────────────────────────────────────────────────────
# load_config / save_config
# ─────────────────────────────────────────────────────────

def test_load_config_creates_defaults_if_missing(axon_home):
    import axon.core as core
    cfg = core.load_config()
    assert "skills" in cfg or "agents" in cfg  # minimal valid structure


def test_save_and_load_config_roundtrip(axon_home):
    import axon.core as core
    core.init_axon_dir()
    original = {"agents": {"cursor": {"local": {"skills": ["ts-rules"]}}}}
    core.save_config(original)
    loaded = core.load_config()
    assert loaded["agents"]["cursor"]["local"]["skills"] == ["ts-rules"]


# ─────────────────────────────────────────────────────────
# update_config_state
# ─────────────────────────────────────────────────────────

def test_update_config_enable_adds_item(axon_home):
    import axon.core as core
    core.init_axon_dir()
    core.update_config_state("cursor", "local", "skills", "my-skill", enable=True)
    cfg = core.load_config()
    assert "my-skill" in cfg["agents"]["cursor"]["local"]["skills"]


def test_update_config_enable_is_idempotent(axon_home):
    import axon.core as core
    core.init_axon_dir()
    core.update_config_state("cursor", "local", "skills", "my-skill", enable=True)
    core.update_config_state("cursor", "local", "skills", "my-skill", enable=True)
    cfg = core.load_config()
    assert cfg["agents"]["cursor"]["local"]["skills"].count("my-skill") == 1


def test_update_config_disable_removes_item(axon_home):
    import axon.core as core
    core.init_axon_dir()
    core.update_config_state("cursor", "local", "skills", "my-skill", enable=True)
    core.update_config_state("cursor", "local", "skills", "my-skill", enable=False)
    cfg = core.load_config()
    assert "my-skill" not in cfg["agents"]["cursor"]["local"]["skills"]


def test_update_config_disable_on_absent_is_noop(axon_home):
    import axon.core as core
    core.init_axon_dir()
    # Should not raise
    core.update_config_state("cursor", "local", "skills", "nonexistent", enable=False)


def test_update_config_creates_nested_keys_automatically(axon_home):
    import axon.core as core
    core.init_axon_dir()
    core.update_config_state("devin", "global", "workflows", "pr-review.md", enable=True)
    cfg = core.load_config()
    assert "pr-review.md" in cfg["agents"]["devin"]["global"]["workflows"]


def test_update_config_multiple_agents_isolated(axon_home):
    import axon.core as core
    core.init_axon_dir()
    core.update_config_state("cursor", "local", "skills", "a", enable=True)
    core.update_config_state("claude", "local", "skills", "b", enable=True)
    cfg = core.load_config()
    assert "a" in cfg["agents"]["cursor"]["local"]["skills"]
    assert "b" not in cfg["agents"]["cursor"]["local"]["skills"]
    assert "b" in cfg["agents"]["claude"]["local"]["skills"]


# ─────────────────────────────────────────────────────────
# get_staged_items
# ─────────────────────────────────────────────────────────

def test_get_staged_items_lists_all_types(axon_home):
    import axon.core as core
    core.init_axon_dir()
    (axon_home / "skills" / "fast-format").mkdir()
    (axon_home / "skills" / "fast-format" / "SKILL.md").write_text("body")
    (axon_home / "principles" / "no-comments.md").write_text("principle")
    (axon_home / "workflows" / "pr-review.md").write_text("workflow")

    items = core.get_staged_items()
    assert "fast-format" in items["skills"]
    assert "no-comments.md" in items["principles"]
    assert "pr-review.md" in items["workflows"]


def test_get_staged_items_skips_ds_store(axon_home):
    import axon.core as core
    core.init_axon_dir()
    (axon_home / "skills" / ".DS_Store").write_text("")
    (axon_home / "principles" / ".DS_Store").write_text("")
    items = core.get_staged_items()
    assert ".DS_Store" not in items["skills"]
    assert ".DS_Store" not in items["principles"]


def test_get_staged_items_empty_when_hub_missing(tmp_path, monkeypatch):
    import axon.core as core
    nonexistent = tmp_path / "no-such-dir"
    monkeypatch.setattr(core, "AXON_DIR", nonexistent)
    monkeypatch.setattr(core, "CONFIG_FILE", nonexistent / "config.yaml")
    items = core.get_staged_items()
    assert items == {"skills": [], "principles": [], "workflows": []}


# ─────────────────────────────────────────────────────────
# stage_skill
# ─────────────────────────────────────────────────────────

def test_stage_skill_from_flat_md(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "my-skill.md"
    src.write_text("---\nname: my-skill\n---\nbody")
    dest = core.stage_skill(src, "my-skill")
    assert dest.is_dir()
    assert (dest / "SKILL.md").is_file()
    assert (dest / "SKILL.md").read_text() == src.read_text()


def test_stage_skill_from_folder_with_skill_md(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "my-skill"
    src.mkdir()
    (src / "SKILL.md").write_text("skill body")
    (src / "scripts").mkdir()
    (src / "scripts" / "run.sh").write_text("#!/bin/bash")

    dest = core.stage_skill(src, "my-skill")
    assert (dest / "SKILL.md").read_text() == "skill body"
    assert (dest / "scripts" / "run.sh").is_file()


def test_stage_skill_from_folder_without_skill_md_renames_single_md(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "tool"
    src.mkdir()
    (src / "tool.md").write_text("the skill")

    dest = core.stage_skill(src, "tool")
    assert (dest / "SKILL.md").is_file()
    assert (dest / "SKILL.md").read_text() == "the skill"


def test_stage_skill_from_folder_without_skill_md_multiple_mds_kept(tmp_path, axon_home):
    """If folder has multiple .md files and no SKILL.md, we keep all as-is (no rename)."""
    import axon.core as core
    src = tmp_path / "multi"
    src.mkdir()
    (src / "a.md").write_text("a")
    (src / "b.md").write_text("b")

    dest = core.stage_skill(src, "multi")
    assert (dest / "a.md").is_file()
    assert (dest / "b.md").is_file()


def test_stage_skill_raises_if_already_exists(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "s.md"
    src.write_text("body")
    core.stage_skill(src, "s")
    with pytest.raises(FileExistsError):
        core.stage_skill(src, "s", overwrite=False)


def test_stage_skill_overwrites_when_flag_set(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "s.md"
    src.write_text("v1")
    core.stage_skill(src, "s")
    src.write_text("v2")
    dest = core.stage_skill(src, "s", overwrite=True)
    assert (dest / "SKILL.md").read_text() == "v2"


# ─────────────────────────────────────────────────────────
# stage_principle
# ─────────────────────────────────────────────────────────

def test_stage_principle_copies_flat_file(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "style.md"
    src.write_text("always write tests")
    dest = core.stage_principle(src, "style.md")
    assert dest.is_file()
    assert dest.read_text() == "always write tests"


def test_stage_principle_raises_for_directory(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "mydir"
    src.mkdir()
    with pytest.raises(ValueError, match="flat files"):
        core.stage_principle(src, "mydir.md")


def test_stage_principle_raises_if_already_exists(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "p.md"
    src.write_text("x")
    core.stage_principle(src, "p.md")
    with pytest.raises(FileExistsError):
        core.stage_principle(src, "p.md", overwrite=False)


def test_stage_principle_overwrites_when_flag_set(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "p.md"
    src.write_text("v1")
    core.stage_principle(src, "p.md")
    src.write_text("v2")
    dest = core.stage_principle(src, "p.md", overwrite=True)
    assert dest.read_text() == "v2"


# ─────────────────────────────────────────────────────────
# stage_workflow
# ─────────────────────────────────────────────────────────

def test_stage_workflow_copies_flat_file(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "deploy.md"
    src.write_text("step 1: build")
    dest = core.stage_workflow(src, "deploy.md")
    assert dest.is_file()
    assert dest.read_text() == "step 1: build"


def test_stage_workflow_raises_for_directory(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "mydir"
    src.mkdir()
    with pytest.raises(ValueError, match="flat files"):
        core.stage_workflow(src, "mydir.md")


def test_stage_workflow_raises_if_already_exists(tmp_path, axon_home):
    import axon.core as core
    src = tmp_path / "w.md"
    src.write_text("x")
    core.stage_workflow(src, "w.md")
    with pytest.raises(FileExistsError):
        core.stage_workflow(src, "w.md", overwrite=False)
