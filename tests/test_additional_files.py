import pytest
from pathlib import Path
from click.testing import CliRunner
from axon.cli import cli
from axon.core import (
    stage_skill,
    get_skill_additional_files,
    add_additional_file_to_skill,
    register_shared_additional_file,
    unregister_shared_additional_file,
    AXON_DIR,
)


def test_get_skill_additional_files_ignores_readme_and_index(tmp_path, monkeypatch):
    monkeypatch.setattr("axon.core.AXON_DIR", tmp_path / ".axon")
    monkeypatch.setattr("axon.cli.AXON_DIR", tmp_path / ".axon")
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("--- \nname: my-skill\n---\nMain body")
    (skill_dir / "README.md").write_text("Skill documentation")
    (skill_dir / "INDEX.md").write_text("Skill index")
    (skill_dir / "schema-code-sync.md").write_text("Extra file")

    add_files = get_skill_additional_files(skill_dir)
    file_names = [f.name for f in add_files]

    assert "schema-code-sync.md" in file_names
    assert "README.md" not in file_names
    assert "INDEX.md" not in file_names
    assert "SKILL.md" not in file_names


def test_add_additional_file_to_skill(tmp_path, monkeypatch):
    monkeypatch.setattr("axon.core.AXON_DIR", tmp_path / ".axon")
    monkeypatch.setattr("axon.cli.AXON_DIR", tmp_path / ".axon")
    src_dir = tmp_path / "src_skill"
    src_dir.mkdir()
    (src_dir / "SKILL.md").write_text("Body")
    staged = stage_skill(src_dir, "sample-skill")

    extra = tmp_path / "CHECKS.md"
    extra.write_text("Checks content")

    dest = add_additional_file_to_skill("sample-skill", extra)
    assert dest.exists()
    assert (staged / "CHECKS.md").exists()


def test_shared_additional_file_registry(tmp_path, monkeypatch):
    monkeypatch.setattr("axon.core.AXON_DIR", tmp_path / ".axon")
    monkeypatch.setattr("axon.cli.AXON_DIR", tmp_path / ".axon")
    register_shared_additional_file("schema.md", "skill-a")
    register_shared_additional_file("schema.md", "skill-b")

    # Unregister skill-a -> file still needed by skill-b
    can_remove = unregister_shared_additional_file("schema.md", "skill-a")
    assert can_remove is False

    # Unregister skill-b -> 0 references left
    can_remove_last = unregister_shared_additional_file("schema.md", "skill-b")
    assert can_remove_last is True


def test_enable_flat_file_agent_links_additional_files(tmp_path, monkeypatch):
    axon_dir = tmp_path / ".axon"
    monkeypatch.setattr("axon.core.AXON_DIR", axon_dir)
    monkeypatch.setattr("axon.cli.AXON_DIR", axon_dir)
    monkeypatch.chdir(tmp_path)

    skill_dir = tmp_path / "openapi-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Main skill")
    (skill_dir / "schema-code-sync.md").write_text("Schema sync")

    runner = CliRunner()
    res = runner.invoke(cli, ["add", str(skill_dir), "--name", "openapi-skill", "--type", "skill"])
    assert res.exit_code == 0

    cursor_dir = tmp_path / ".cursor" / "rules"
    cursor_dir.mkdir(parents=True)
    mock_adapters = {
        "cursor": type("Adapter", (), {
            "name": "Cursor",
            "skill_format": "flat_mdc",
            "uses_skill_folders": False,
            "supports_skills": True,
            "supports_compile": False,
            "local_workflow_dirs": [],
            "get_skill_suffix": lambda self: ".mdc",
            "get_dir_paths": lambda self, t, is_global=False: [cursor_dir],
            "get_opposite_dir_paths": lambda self, t, is_global=False: [],
        })()
    }
    monkeypatch.setattr("axon.adapters.ADAPTERS", mock_adapters)
    monkeypatch.setattr("axon.cli.ADAPTERS", mock_adapters)

    res_enable = runner.invoke(cli, ["enable", "openapi-skill", "--agent", "cursor"])
    assert res_enable.exit_code == 0
    assert (cursor_dir / "openapi-skill.mdc").exists()
    assert (cursor_dir / "schema-code-sync.md").exists()
