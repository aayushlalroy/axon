import os
import shutil
import pytest
from pathlib import Path
from click.testing import CliRunner
from axon.cli import cli
from axon.core import get_staged_items, load_config, AXON_DIR


@pytest.fixture(autouse=True)
def setup_sandbox(tmp_path, monkeypatch):
    """
    Creates an isolated sandbox environment for every test in this matrix:
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


def test_sandbox_e2e_init_all_and_specific_agents(setup_sandbox):
    """E2E Test: 'axon init' across all agents and specific agent combinations."""
    runner = CliRunner()

    # Init all agents
    res = runner.invoke(cli, ["init"])
    assert res.exit_code == 0
    proj = setup_sandbox["project_dir"]

    assert (proj / ".cursor" / "rules").is_dir()
    assert (proj / ".claude" / "skills").is_dir()
    assert (proj / ".agents" / "skills").is_dir()
    assert (proj / ".devin" / "skills").is_dir()
    assert (proj / ".codex" / "skills").is_dir()
    assert (proj / ".windsurf" / "rules").is_dir()
    assert (proj / ".github" / "instructions").is_dir()
    assert (proj / "AGENTS.md").is_file()
    assert (proj / "CLAUDE.md").is_file()

    # Re-init specific agent
    res2 = runner.invoke(cli, ["init", "--agent", "cursor"])
    assert res2.exit_code == 0


def test_sandbox_e2e_add_permutations(setup_sandbox):
    """E2E Test: 'axon add' with single files, folders, additional files, and multi-types."""
    runner = CliRunner()
    tmp = setup_sandbox["tmp_path"]

    # 1. Add single skill file
    skill_file = tmp / "my-single-skill.md"
    skill_file.write_text("---\nname: my-single-skill\n---\nSingle skill content")
    res1 = runner.invoke(cli, ["add", str(skill_file), "--type", "skill"])
    assert res1.exit_code == 0
    assert (setup_sandbox["axon_dir"] / "skills" / "my-single-skill" / "SKILL.md").is_file()

    # 2. Add folder skill with additional files and ignored README.md/INDEX.md
    skill_folder = tmp / "openapi-contract-first"
    skill_folder.mkdir()
    (skill_folder / "SKILL.md").write_text("Main skill body")
    (skill_folder / "schema-code-sync.md").write_text("Auxiliary schema file")
    (skill_folder / "README.md").write_text("Should be ignored")
    (skill_folder / "INDEX.md").write_text("Should be ignored")

    res2 = runner.invoke(cli, ["add", str(skill_folder), "--type", "skill"])
    assert res2.exit_code == 0
    staged_skill = setup_sandbox["axon_dir"] / "skills" / "openapi-contract-first"
    assert (staged_skill / "SKILL.md").is_file()
    assert (staged_skill / "schema-code-sync.md").is_file()
    # Ensure ignored files were excluded
    assert not (staged_skill / "README.md").exists()
    assert not (staged_skill / "INDEX.md").exists()

    # 3. Add principle file
    p_file = tmp / "coding-standards.md"
    p_file.write_text("No global state")
    res3 = runner.invoke(cli, ["add", str(p_file), "--type", "principle"])
    assert res3.exit_code == 0
    assert (setup_sandbox["axon_dir"] / "principles" / "coding-standards.md").is_file()

    # 4. Add workflow file
    w_file = tmp / "release-flow.md"
    w_file.write_text("Release steps")
    res4 = runner.invoke(cli, ["add", str(w_file), "--type", "workflow"])
    assert res4.exit_code == 0
    assert (setup_sandbox["axon_dir"] / "workflows" / "release-flow.md").is_file()

    # 5. Append file to existing skill via --skill
    extra_file = tmp / "CHECKS.md"
    extra_file.write_text("Extra checks")
    res5 = runner.invoke(cli, ["add", str(extra_file), "--skill", "openapi-contract-first"])
    assert res5.exit_code == 0
    assert (staged_skill / "CHECKS.md").is_file()

    # 6. Multi-type staging (skill + principle)
    multi_file = tmp / "dual-role.md"
    multi_file.write_text("Dual role content")
    res6 = runner.invoke(cli, ["add", str(multi_file), "--name", "dual-role", "--type", "skill", "--type", "principle"])
    assert res6.exit_code == 0
    assert (setup_sandbox["axon_dir"] / "skills" / "dual-role" / "SKILL.md").is_file()
    assert (setup_sandbox["axon_dir"] / "principles" / "dual-role.md").is_file()


def test_sandbox_e2e_import_permutations(setup_sandbox):
    """E2E Test: 'axon import' across folder structures, manifests, name-sources, dry-runs, and skip-on-existing."""
    runner = CliRunner()
    tmp = setup_sandbox["tmp_path"]

    # Build source assets tree
    assets_dir = tmp / "assets"
    skills_dir = assets_dir / "skills" / "spring-doctor"
    principles_dir = assets_dir / "principles"
    workflows_dir = assets_dir / "workflows"

    skills_dir.mkdir(parents=True)
    principles_dir.mkdir(parents=True)
    workflows_dir.mkdir(parents=True)

    (skills_dir / "SKILL.md").write_text("Spring doctor skill")
    (skills_dir / "CHECKS.md").write_text("Spring checks")
    (skills_dir / "README.md").write_text("Ignored README")

    (principles_dir / "claim-tagging.md").write_text("Claim tagging principle")
    (principles_dir / "INDEX.md").write_text("Ignored INDEX")

    (workflows_dir / "deploy-pipe.md").write_text("Deploy pipeline workflow")

    # 1. Dry-run import
    res_dry = runner.invoke(cli, ["import", str(assets_dir), "--dry-run"])
    assert res_dry.exit_code == 0
    assert "Would Stage" in res_dry.output
    assert "spring-doctor" not in get_staged_items()["skills"]

    # 2. Directory auto-scan import
    res_import = runner.invoke(cli, ["import", str(assets_dir)])
    assert res_import.exit_code == 0
    staged = get_staged_items()
    assert "spring-doctor" in staged["skills"]
    assert "claim-tagging.md" in staged["principles"] or "claim-tagging" in staged["principles"]
    assert "deploy-pipe.md" in staged["workflows"] or "deploy-pipe" in staged["workflows"]

    # Verify additional file was staged and ignored files excluded
    staged_spring = setup_sandbox["axon_dir"] / "skills" / "spring-doctor"
    assert (staged_spring / "CHECKS.md").is_file()
    assert not (staged_spring / "README.md").exists()

    # 3. Repeat import (Idempotency: "just append, no overwrite")
    res_repeat = runner.invoke(cli, ["import", str(assets_dir)])
    assert res_repeat.exit_code == 0
    assert "Skipped" in res_repeat.output

    # 4. Manifest configuration import with custom ignore pattern
    manifest_dir = tmp / "manifest_assets"
    m_skills = manifest_dir / "skills" / "custom-skill"
    m_skills.mkdir(parents=True)
    (m_skills / "SKILL.md").write_text("Custom skill body")
    (m_skills / "file.draft.md").write_text("Draft file")

    manifest_yaml = manifest_dir / "axon-import.yaml"
    manifest_yaml.write_text("""
name_source: folder
ignore:
  - "*.draft.md"
skills:
  - path: skills/custom-skill
    name: renamed-custom-skill
""")

    res_manifest = runner.invoke(cli, ["import", str(manifest_dir), "--config", str(manifest_yaml)])
    assert res_manifest.exit_code == 0
    assert "renamed-custom-skill" in get_staged_items()["skills"]
    staged_custom = setup_sandbox["axon_dir"] / "skills" / "renamed-custom-skill"
    assert not (staged_custom / "file.draft.md").exists()


def test_sandbox_e2e_enable_disable_matrix_across_all_adapters(setup_sandbox):
    """E2E Test: 'axon enable' and 'axon disable' across all adapters (folder vs flat file)."""
    runner = CliRunner()
    tmp = setup_sandbox["tmp_path"]
    proj = setup_sandbox["project_dir"]

    # Stage skill with additional file
    skill_dir = tmp / "openapi-contract-first"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Main skill")
    (skill_dir / "schema-code-sync.md").write_text("Auxiliary schema")
    runner.invoke(cli, ["add", str(skill_dir), "--name", "openapi-contract-first", "--type", "skill"])

    # Stage principle
    p_file = tmp / "claim-tagging.md"
    p_file.write_text("Tag claims inline")
    runner.invoke(cli, ["add", str(p_file), "--name", "claim-tagging", "--type", "principle"])

    # Init project
    runner.invoke(cli, ["init"])

    # 1. Enable skill for Cursor (flat_mdc)
    res_cursor = runner.invoke(cli, ["enable", "openapi-contract-first", "--agent", "cursor"])
    assert res_cursor.exit_code == 0
    cursor_rules = proj / ".cursor" / "rules"
    assert (cursor_rules / "openapi-contract-first.mdc").is_symlink()
    # Additional file MUST be linked into .cursor/rules/
    assert (cursor_rules / "schema-code-sync.md").is_symlink()

    # 2. Enable skill for Claude Code (folder_skill_md)
    res_claude = runner.invoke(cli, ["enable", "openapi-contract-first", "--agent", "claude"])
    assert res_claude.exit_code == 0
    claude_skills = proj / ".claude" / "skills" / "openapi-contract-first"
    assert claude_skills.is_symlink()
    assert (claude_skills / "schema-code-sync.md").is_file()

    # 3. Enable principle for supports_compile agents (compiles into AGENTS.md / CLAUDE.md)
    res_p = runner.invoke(cli, ["enable", "principle", "claim-tagging", "--agent", "claude"])
    assert res_p.exit_code == 0
    claude_md = (proj / "CLAUDE.md").read_text(encoding="utf-8")
    assert "claim-tagging" in claude_md
    assert "Tag claims inline" in claude_md

    # 4. Disable skill
    res_dis = runner.invoke(cli, ["disable", "openapi-contract-first", "--agent", "cursor"])
    assert res_dis.exit_code == 0
    assert not (cursor_rules / "openapi-contract-first.mdc").exists()
    assert not (cursor_rules / "schema-code-sync.md").exists()


def test_sandbox_e2e_multi_type_validation_and_disambiguation(setup_sandbox):
    """E2E Test: Strict type prefix validation and error reporting when calling enable with wrong type."""
    runner = CliRunner()
    tmp = setup_sandbox["tmp_path"]

    # Stage item strictly as a skill
    skill_file = tmp / "my-only-skill.md"
    skill_file.write_text("Skill body")
    runner.invoke(cli, ["add", str(skill_file), "--name", "my-only-skill", "--type", "skill"])

    # Enable with invalid explicit type 'principle' -> MUST report explicit warning/error!
    res_invalid = runner.invoke(cli, ["enable", "principle", "my-only-skill"])
    assert "staged as a skill, not a principle" in res_invalid.output or "Warning" in res_invalid.output


def test_sandbox_e2e_activate_deactivate_local_overrides(setup_sandbox):
    """E2E Test: 'axon activate' and 'axon deactivate' with local file overrides."""
    runner = CliRunner()
    tmp = setup_sandbox["tmp_path"]
    proj = setup_sandbox["project_dir"]

    # Stage skill
    skill_dir = tmp / "interactive-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\ndisable-model-invocation: false\n---\nSkill body")
    runner.invoke(cli, ["add", str(skill_dir), "--name", "interactive-skill", "--type", "skill"])

    runner.invoke(cli, ["init"])
    runner.invoke(cli, ["enable", "interactive-skill", "--agent", "cursor"])

    cursor_rule = proj / ".cursor" / "rules" / "interactive-skill.mdc"
    assert cursor_rule.is_symlink()

    # Deactivate locally (creates physical local file override)
    res_deact = runner.invoke(cli, ["deactivate", "interactive-skill", "--agent", "cursor"])
    assert res_deact.exit_code == 0
    assert "Deactivated" in res_deact.output
    # Must now be a physical local override file (not a symlink)
    assert cursor_rule.is_file() and not cursor_rule.is_symlink()
    text = cursor_rule.read_text(encoding="utf-8")
    assert "disable-model-invocation: true" in text or "disable_model_invocation: true" in text

    # Activate locally again
    res_act = runner.invoke(cli, ["activate", "interactive-skill", "--agent", "cursor"])
    assert res_act.exit_code == 0
    assert "Activated" in res_act.output
    text_act = cursor_rule.read_text(encoding="utf-8")
    assert "disable-model-invocation: false" in text_act or "disable_model_invocation: false" in text_act


def test_sandbox_e2e_remove_purges_everything(setup_sandbox):
    """E2E Test: 'axon remove' purges staged hub files, symlinks, physical local overrides, and config state."""
    runner = CliRunner()
    tmp = setup_sandbox["tmp_path"]
    proj = setup_sandbox["project_dir"]

    # Stage skill with auxiliary file
    skill_dir = tmp / "purge-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Purge body")
    (skill_dir / "AUX.md").write_text("Aux file")
    runner.invoke(cli, ["add", str(skill_dir), "--name", "purge-skill", "--type", "skill"])

    runner.invoke(cli, ["init"])
    runner.invoke(cli, ["enable", "purge-skill", "--agent", "cursor"])
    runner.invoke(cli, ["deactivate", "purge-skill", "--agent", "cursor"])

    cursor_rule = proj / ".cursor" / "rules" / "purge-skill.mdc"
    aux_rule = proj / ".cursor" / "rules" / "AUX.md"
    assert cursor_rule.exists()
    assert aux_rule.exists()

    # Run axon remove
    res_rem = runner.invoke(cli, ["remove", "purge-skill", "-y"])
    assert res_rem.exit_code == 0
    assert "Removed" in res_rem.output

    # Verify everything was purged
    assert "purge-skill" not in get_staged_items()["skills"]
    assert not (setup_sandbox["axon_dir"] / "skills" / "purge-skill").exists()
    assert not cursor_rule.exists()
    assert not aux_rule.exists()


def test_sandbox_e2e_shared_additional_files_reference_counter(setup_sandbox):
    """E2E Test: Shared auxiliary files between Skill A & Skill B are preserved until both are disabled."""
    runner = CliRunner()
    tmp = setup_sandbox["tmp_path"]
    proj = setup_sandbox["project_dir"]

    # Skill A
    dir_a = tmp / "skill-a"
    dir_a.mkdir()
    (dir_a / "SKILL.md").write_text("Skill A")
    (dir_a / "shared-helper.md").write_text("Shared helper logic")
    runner.invoke(cli, ["add", str(dir_a), "--name", "skill-a", "--type", "skill"])

    # Skill B
    dir_b = tmp / "skill-b"
    dir_b.mkdir()
    (dir_b / "SKILL.md").write_text("Skill B")
    (dir_b / "shared-helper.md").write_text("Shared helper logic")
    runner.invoke(cli, ["add", str(dir_b), "--name", "skill-b", "--type", "skill"])

    runner.invoke(cli, ["init"])
    runner.invoke(cli, ["enable", "skill-a", "--agent", "cursor"])
    runner.invoke(cli, ["enable", "skill-b", "--agent", "cursor"])

    cursor_rules = proj / ".cursor" / "rules"
    assert (cursor_rules / "skill-a.mdc").exists()
    assert (cursor_rules / "skill-b.mdc").exists()
    assert (cursor_rules / "shared-helper.md").exists()

    # Disable Skill A -> shared-helper.md MUST REMAIN because Skill B still needs it!
    runner.invoke(cli, ["disable", "skill-a", "--agent", "cursor"])
    assert not (cursor_rules / "skill-a.mdc").exists()
    assert (cursor_rules / "skill-b.mdc").exists()
    assert (cursor_rules / "shared-helper.md").exists()

    # Disable Skill B -> NOW shared-helper.md should be removed!
    runner.invoke(cli, ["disable", "skill-b", "--agent", "cursor"])
    assert not (cursor_rules / "skill-b.mdc").exists()
    assert not (cursor_rules / "shared-helper.md").exists()
