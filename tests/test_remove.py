import pytest
from pathlib import Path
from click.testing import CliRunner
from axon.cli import cli
from axon.core import get_staged_items, stage_skill, stage_principle


def test_remove_command_removes_staged_skill(tmp_path, monkeypatch):
    axon_dir = tmp_path / ".axon"
    monkeypatch.setattr("axon.core.AXON_DIR", axon_dir)
    monkeypatch.setattr("axon.cli.AXON_DIR", axon_dir)

    skill_dir = tmp_path / "target-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Skill body")

    stage_skill(skill_dir, "target-skill")
    assert "target-skill" in get_staged_items()["skills"]

    runner = CliRunner()
    res = runner.invoke(cli, ["remove", "target-skill", "-y"])
    assert res.exit_code == 0

    assert "target-skill" not in get_staged_items()["skills"]
    assert not (axon_dir / "skills" / "target-skill").exists()


def test_remove_command_removes_staged_principle(tmp_path, monkeypatch):
    axon_dir = tmp_path / ".axon"
    monkeypatch.setattr("axon.core.AXON_DIR", axon_dir)
    monkeypatch.setattr("axon.cli.AXON_DIR", axon_dir)

    principle_file = tmp_path / "my-principle.md"
    principle_file.write_text("Principle body")

    stage_principle(principle_file, "my-principle.md")
    assert "my-principle.md" in get_staged_items()["principles"] or "my-principle" in get_staged_items()["principles"]

    runner = CliRunner()
    res = runner.invoke(cli, ["remove", "principle", "my-principle", "-y"])
    assert res.exit_code == 0

    staged = get_staged_items()
    assert "my-principle.md" not in staged["principles"]
    assert "my-principle" not in staged["principles"]
    assert not (axon_dir / "principles" / "my-principle.md").exists()
