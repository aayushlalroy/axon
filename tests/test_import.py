import pytest
from pathlib import Path
from click.testing import CliRunner
from axon.cli import cli
from axon.core import get_staged_items


def test_import_command_scans_directory(tmp_path, monkeypatch):
    monkeypatch.setattr("axon.core.AXON_DIR", tmp_path / ".axon")

    import_root = tmp_path / "assets"
    skills_dir = import_root / "skills" / "clarify-first"
    principles_dir = import_root / "principles"
    skills_dir.mkdir(parents=True)
    principles_dir.mkdir(parents=True)

    (skills_dir / "SKILL.md").write_text("--- \nname: clarify-first\n---\nBody")
    (skills_dir / "README.md").write_text("Should be ignored")
    (principles_dir / "claim-tagging.md").write_text("Principle body")

    runner = CliRunner()
    res = runner.invoke(cli, ["import", str(import_root)])
    assert res.exit_code == 0
    assert "Import complete" in res.output

    staged = get_staged_items()
    assert "clarify-first" in staged["skills"]
    assert "claim-tagging.md" in staged["principles"] or "claim-tagging" in staged["principles"]


def test_import_command_skips_already_staged(tmp_path, monkeypatch):
    monkeypatch.setattr("axon.core.AXON_DIR", tmp_path / ".axon")

    import_root = tmp_path / "assets"
    skills_dir = import_root / "skills" / "clarify-first"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("--- \nname: clarify-first\n---\nBody")

    runner = CliRunner()
    # First import
    runner.invoke(cli, ["import", str(import_root)])

    # Second import -> should skip without error ("just append, no overwrite")
    res = runner.invoke(cli, ["import", str(import_root)])
    assert res.exit_code == 0
    assert "Skipped" in res.output or "Already Staged" in res.output


def test_import_command_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr("axon.core.AXON_DIR", tmp_path / ".axon")

    import_root = tmp_path / "assets"
    skills_dir = import_root / "skills" / "sample-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("Main skill")

    runner = CliRunner()
    res = runner.invoke(cli, ["import", str(import_root), "--dry-run"])
    assert res.exit_code == 0
    assert "Would Stage" in res.output

    staged = get_staged_items()
    assert "sample-skill" not in staged["skills"]
