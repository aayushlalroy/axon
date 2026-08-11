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
