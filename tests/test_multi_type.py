import pytest
from pathlib import Path
from click.testing import CliRunner
from axon.cli import cli
from axon.core import get_staged_types_for_item, normalize_name


def test_normalize_name():
    assert normalize_name("claim-tagging.md") == "claim-tagging"
    assert normalize_name("claim-tagging.mdc") == "claim-tagging"
    assert normalize_name("claim-tagging") == "claim-tagging"


def test_stage_same_item_as_skill_and_principle(tmp_path, monkeypatch):
    monkeypatch.setattr("axon.core.AXON_DIR", tmp_path / ".axon")

    src = tmp_path / "my-rule.md"
    src.write_text("--- \nname: my-rule\n---\nRule content")

    runner = CliRunner()
    res = runner.invoke(cli, ["add", str(src), "--name", "my-rule", "--type", "skill"])
    assert res.exit_code == 0

    res2 = runner.invoke(cli, ["add", str(src), "--name", "my-rule", "--type", "principle"])
    assert res2.exit_code == 0

    staged_types = get_staged_types_for_item("my-rule")
    assert "skill" in staged_types
    assert "principle" in staged_types


def test_enable_explicit_type_mismatch_error(tmp_path, monkeypatch):
    monkeypatch.setattr("axon.core.AXON_DIR", tmp_path / ".axon")

    src = tmp_path / "skill-only.md"
    src.write_text("Skill content")

    runner = CliRunner()
    runner.invoke(cli, ["add", str(src), "--name", "skill-only", "--type", "skill"])

    # Try to enable as principle -> should fail with explicit error message
    res = runner.invoke(cli, ["enable", "principle", "skill-only"])
    assert "staged as a skill, not a principle" in res.output or res.exit_code != 0


def test_enable_all_multi_type_only_targets_actual_staged_types(tmp_path, monkeypatch):
    monkeypatch.setattr("axon.core.AXON_DIR", tmp_path / ".axon")

    # Stage as skill and principle ONLY (not workflow)
    skill_dir = tmp_path / "doc-version-sync"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Skill content")

    principle_file = tmp_path / "doc-version-sync.md"
    principle_file.write_text("Principle content")

    runner = CliRunner()
    runner.invoke(cli, ["add", str(skill_dir), "--name", "doc-version-sync", "--type", "skill"])
    runner.invoke(cli, ["add", str(principle_file), "--name", "doc-version-sync", "--type", "principle"])

    # Enable doc-version-sync and select '3' for all
    res = runner.invoke(cli, ["enable", "doc-version-sync"], input="3\n")
    assert res.exit_code == 0
    assert "Enabled 'doc-version-sync' (skill)" in res.output
    assert "Enabled 'doc-version-sync' (principle)" in res.output
    assert "Staged path" not in res.output  # No workflow missing error!
