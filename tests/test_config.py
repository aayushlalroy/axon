import pytest
from pathlib import Path
from axon.core import should_ignore_file, normalize_name


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
