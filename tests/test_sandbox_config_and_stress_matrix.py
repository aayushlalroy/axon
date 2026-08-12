import os
import shutil
import pytest
import yaml
from pathlib import Path
from click.testing import CliRunner
from axon.cli import cli
from axon.core import (
    get_staged_items,
    load_config,
    save_config,
    AXON_DIR,
    should_ignore_file,
    get_config_file,
)


@pytest.fixture(autouse=True)
def setup_stress_sandbox(tmp_path, monkeypatch):
    """
    Creates an isolated sandbox environment for config and stress testing:
    - Custom ~/.axon staging hub at tmp_path/.axon
    - Custom working directory at tmp_path/project
    - Custom home directory at tmp_path/home
    """
    axon_dir = tmp_path / ".axon"
    home_dir = tmp_path / "home"
    project_dir = tmp_path / "project"

    axon_dir.mkdir(parents=True, exist_ok=True)
    home_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("axon.core.AXON_DIR", axon_dir)
    monkeypatch.setattr("axon.cli.AXON_DIR", axon_dir)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_dir)

    return {
        "axon_dir": axon_dir,
        "home_dir": home_dir,
        "project_dir": project_dir,
        "tmp_path": tmp_path,
    }


# ==============================================================================
# SECTION 1: CONFIGURATION MUTATIONS & PERMUTATIONS
# ==============================================================================

def test_config_ignore_patterns_single_multiple_all(setup_stress_sandbox):
    """
    Test modifying defaults.ignore_patterns in ~/.axon/config.yaml dynamically
    with 1, multiple, and all glob pattern combinations.
    """
    runner = CliRunner()
    tmp = setup_stress_sandbox["tmp_path"]

    # Create source skill folder with various files
    src = tmp / "config-ignore-skill"
    src.mkdir()
    (src / "SKILL.md").write_text("Main skill body")
    (src / "normal-file.md").write_text("Normal file")
    (src / "draft-doc.draft.md").write_text("Draft doc")
    (src / "SECRET.key").write_text("Secret key")
    (src / "temp-build.tmp").write_text("Temp build")

    # 1. Test single custom ignore pattern in config
    cfg = load_config()
    cfg["defaults"] = {"ignore_patterns": ["*.draft.md"]}
    save_config(cfg)

    runner.invoke(cli, ["add", str(src), "--name", "skill-single-ignore", "--type", "skill"])
    staged_1 = setup_stress_sandbox["axon_dir"] / "skills" / "skill-single-ignore"
    assert (staged_1 / "normal-file.md").exists()
    assert (staged_1 / "SECRET.key").exists()
    assert not (staged_1 / "draft-doc.draft.md").exists()

    # 2. Test multiple custom ignore patterns in config
    cfg["defaults"]["ignore_patterns"] = ["*.draft.md", "*.key", "*.tmp"]
    save_config(cfg)

    runner.invoke(cli, ["add", str(src), "--name", "skill-multi-ignore", "--type", "skill"])
    staged_2 = setup_stress_sandbox["axon_dir"] / "skills" / "skill-multi-ignore"
    assert (staged_2 / "normal-file.md").exists()
    assert not (staged_2 / "draft-doc.draft.md").exists()
    assert not (staged_2 / "SECRET.key").exists()
    assert not (staged_2 / "temp-build.tmp").exists()


def test_config_name_source_strategies_permutations(setup_stress_sandbox):
    """
    Test name_source strategies: auto | frontmatter | folder | file across imports and adds.
    """
    runner = CliRunner()
    tmp = setup_stress_sandbox["tmp_path"]

    # Create source file with explicit YAML frontmatter name
    src_file = tmp / "original-filename.md"
    src_file.write_text("---\nname: fm-extracted-name\n---\nBody")

    # 1. Test frontmatter strategy
    res_fm = runner.invoke(cli, ["add", str(src_file), "--type", "skill"])
    assert res_fm.exit_code == 0
    assert "fm-extracted-name" in get_staged_items()["skills"]

    # 2. Test folder name strategy in import manifest
    import_dir = tmp / "import_tree"
    skill_sub = import_dir / "skills" / "folder-defined-name"
    skill_sub.mkdir(parents=True)
    (skill_sub / "SKILL.md").write_text("---\nname: ignore-fm-name\n---\nBody")

    manifest = import_dir / "axon-import.yaml"
    manifest.write_text("""
name_source: folder
skills:
  - path: skills/folder-defined-name
""")

    res_imp = runner.invoke(cli, ["import", str(import_dir), "--config", str(manifest)])
    assert res_imp.exit_code == 0
    assert "folder-defined-name" in get_staged_items()["skills"]


def test_config_malformed_yaml_and_invalid_files(setup_stress_sandbox):
    """Stress Test: Malformed YAML manifests, missing files, and invalid options."""
    runner = CliRunner()
    tmp = setup_stress_sandbox["tmp_path"]

    # 1. Non-existent manifest file passed to import (Click validation returns non-zero)
    res_missing = runner.invoke(cli, ["import", str(tmp), "--config", str(tmp / "nonexistent.yaml")])
    assert res_missing.exit_code != 0

    # 2. Corrupted malformed YAML file
    bad_yaml = tmp / "bad.yaml"
    bad_yaml.write_text("skills:\n  - path: [unclosed list")
    res_bad = runner.invoke(cli, ["import", str(tmp), "--config", str(bad_yaml)])
    assert "Error parsing manifest" in res_bad.output or res_bad.exit_code != 0


# ==============================================================================
# SECTION 2: COMMAND FLOW STRESS & BREAKING SCENARIO MATRIX
# ==============================================================================

def test_stress_add_edge_cases(setup_stress_sandbox):
    """Stress Test: Edge cases for 'axon add' command."""
    runner = CliRunner()
    tmp = setup_stress_sandbox["tmp_path"]

    # 1. Non-existent source path
    res_nonexist = runner.invoke(cli, ["add", str(tmp / "does-not-exist.md"), "--type", "skill"])
    assert res_nonexist.exit_code != 0 or "Error" in res_nonexist.output

    # 2. Adding skill with special characters and dashes
    special_file = tmp / "my_special-skill.v1.md"
    special_file.write_text("Special content")
    res_spec = runner.invoke(cli, ["add", str(special_file), "--type", "skill"])
    assert res_spec.exit_code == 0
    assert "my_special-skill.v1" in get_staged_items()["skills"] or "my_special-skill" in get_staged_items()["skills"]

    # 3. Duplicate add overwrites cleanly
    res_dup = runner.invoke(cli, ["add", str(special_file), "--type", "skill"])
    assert res_dup.exit_code == 0
    assert "Staged" in res_dup.output

    # 4. Appending additional file to non-existent skill
    extra = tmp / "EXTRA.md"
    extra.write_text("Extra content")
    res_extra_err = runner.invoke(cli, ["add", str(extra), "--skill", "non-existent-skill"])
    assert "Error" in res_extra_err.output


def test_stress_enable_disable_edge_cases(setup_stress_sandbox):
    """Stress Test: Edge cases for 'axon enable' and 'axon disable'."""
    runner = CliRunner()
    tmp = setup_stress_sandbox["tmp_path"]
    proj = setup_stress_sandbox["project_dir"]

    runner.invoke(cli, ["init"])

    # 1. Enable item that does NOT exist -> graceful error
    res_noitem = runner.invoke(cli, ["enable", "ghost-item"])
    assert "Staged path" in res_noitem.output or "Error" in res_noitem.output or "not found" in res_noitem.output

    # 2. Enable with invalid target agent name -> graceful warning
    skill_dir = tmp / "valid-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Valid skill body")
    runner.invoke(cli, ["add", str(skill_dir), "--name", "valid-skill", "--type", "skill"])

    res_fake_ag = runner.invoke(cli, ["enable", "valid-skill", "--agent", "nonexistent-agent"])
    assert "not supported" in res_fake_ag.output or "Unknown agent" in res_fake_ag.output

    # 3. Enable for GitHub Copilot (does not support skills) -> skipped gracefully
    res_copilot = runner.invoke(cli, ["enable", "valid-skill", "--agent", "copilot"])
    assert "does not support discrete skill files" in res_copilot.output

    # 4. Enable principle and verify compilation into AGENTS.md / CLAUDE.md
    p_file = tmp / "rule-a.md"
    p_file.write_text("Rule A instructions")
    runner.invoke(cli, ["add", str(p_file), "--name", "rule-a", "--type", "principle"])

    runner.invoke(cli, ["enable", "principle", "rule-a", "--agent", "claude"])
    claude_md = (proj / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Rule A instructions" in claude_md

    # Disable principle and verify removal from CLAUDE.md
    runner.invoke(cli, ["disable", "principle", "rule-a", "--agent", "claude"])
    claude_md_after = (proj / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Rule A instructions" not in claude_md_after


def test_stress_multi_type_coexistence_and_partial_removal(setup_stress_sandbox):
    """Stress Test: Item staged as BOTH skill and principle. Disabling/removing principle leaves skill intact."""
    runner = CliRunner()
    tmp = setup_stress_sandbox["tmp_path"]
    proj = setup_stress_sandbox["project_dir"]

    # Stage item as BOTH skill and principle
    dual_file = tmp / "dual-asset.md"
    dual_file.write_text("Dual asset instructions")
    runner.invoke(cli, ["add", str(dual_file), "--name", "dual-asset", "--type", "skill", "--type", "principle"])

    runner.invoke(cli, ["init"])

    # Enable skill for cursor
    runner.invoke(cli, ["enable", "skill", "dual-asset", "--agent", "cursor"])
    cursor_rules = proj / ".cursor" / "rules"
    assert (cursor_rules / "dual-asset.mdc").exists()

    # Enable principle for cursor
    runner.invoke(cli, ["enable", "principle", "dual-asset", "--agent", "cursor"])

    # Remove ONLY the principle type via axon remove principle dual-asset -y
    res_rem_p = runner.invoke(cli, ["remove", "principle", "dual-asset", "-y"])
    assert res_rem_p.exit_code == 0

    staged = get_staged_items()
    # Skill MUST remain staged, principle MUST be un-staged!
    assert "dual-asset" in staged["skills"]
    assert "dual-asset.md" not in staged["principles"]
    assert "dual-asset" not in staged["principles"]

    # Skill symlink in .cursor/rules MUST remain intact!
    assert (cursor_rules / "dual-asset.mdc").exists()


def test_stress_sync_and_list_recovery(setup_stress_sandbox):
    """Stress Test: 'axon list --all', 'axon list --agent', and 'axon sync' symlink recovery."""
    runner = CliRunner()
    tmp = setup_stress_sandbox["tmp_path"]
    proj = setup_stress_sandbox["project_dir"]

    # Stage items
    s_dir = tmp / "sync-skill"
    s_dir.mkdir()
    (s_dir / "SKILL.md").write_text("Sync skill body")
    (s_dir / "helper.md").write_text("Helper body")
    runner.invoke(cli, ["add", str(s_dir), "--name", "sync-skill", "--type", "skill"])

    runner.invoke(cli, ["init"])
    runner.invoke(cli, ["enable", "sync-skill", "--agent", "cursor"])

    cursor_rules = proj / ".cursor" / "rules"
    link_1 = cursor_rules / "sync-skill.mdc"
    link_2 = cursor_rules / "helper.md"
    assert link_1.exists()
    assert link_2.exists()

    # Manually delete symlinks from project directory to simulate corruption
    link_1.unlink()
    link_2.unlink()
    assert not link_1.exists()

    # Run axon sync -y -> MUST recover all deleted symlinks from config.yaml!
    res_sync = runner.invoke(cli, ["sync", "-y"])
    assert res_sync.exit_code == 0
    assert link_1.exists()
    assert link_2.exists()

    # Test axon list --all and axon list --agent cursor
    res_list_all = runner.invoke(cli, ["list", "--all"])
    assert res_list_all.exit_code == 0
    assert "sync-skill" in res_list_all.output

    res_list_cursor = runner.invoke(cli, ["list", "--agent", "cursor"])
    assert res_list_cursor.exit_code == 0
    assert "sync-skill" in res_list_cursor.output
