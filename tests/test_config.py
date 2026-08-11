import pytest
from pathlib import Path
from click.testing import CliRunner
from axon.cli import cli, _resolve_scope
from axon.core import should_ignore_file, normalize_name, extract_name_from_source, save_config, load_config


def test_should_ignore_file_defaults():
    assert should_ignore_file(Path("README.md")) is True
    assert should_ignore_file(Path("INDEX.md")) is True
    assert should_ignore_file(Path(".DS_Store")) is True
    assert should_ignore_file(Path("SKILL.md")) is False
    assert should_ignore_file(Path("schema-code-sync.md")) is False


def test_should_ignore_file_custom_patterns():
    custom = ["*.draft.md", "temp.txt"]
    assert should_ignore_file(Path("doc.draft.md"), custom_ignores=custom) is True
    assert should_ignore_file(Path("temp.txt"), custom_ignores=custom) is True
    assert should_ignore_file(Path("valid.md"), custom_ignores=custom) is False


def test_normalize_name_handles_extensions():
    assert normalize_name("skill-name.md") == "skill-name"
    assert normalize_name("skill-name.mdc") == "skill-name"
    assert normalize_name("skill-name") == "skill-name"
    assert normalize_name("") == ""


def test_config_defaults_name_source_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr("axon.core.AXON_DIR", tmp_path / ".axon")
    src = tmp_path / "folder-name" / "SKILL.md"
    src.parent.mkdir(parents=True)
    src.write_text("---\nname: fm-name\n---\nBody")

    # Default auto strategy returns frontmatter name
    assert extract_name_from_source(src.parent) == "fm-name"

    # Set defaults.name_source = 'folder' in config
    cfg = load_config()
    cfg["defaults"] = {"name_source": "folder"}
    save_config(cfg)

    # Calling extract_name_from_source with default 'auto' now uses config default 'folder'
    assert extract_name_from_source(src.parent) == "folder-name"


def test_config_defaults_scope_resolution(tmp_path, monkeypatch):
    monkeypatch.setattr("axon.core.AXON_DIR", tmp_path / ".axon")

    # When is_global_flag is False and no config set -> scope is False (local)
    assert _resolve_scope(False) is False
    assert _resolve_scope(True) is True

    # Set defaults.scope = 'global' in config
    cfg = load_config()
    cfg["defaults"] = {"scope": "global"}
    save_config(cfg)

    # Now _resolve_scope(False) picks up global default from config
    assert _resolve_scope(False) is True
