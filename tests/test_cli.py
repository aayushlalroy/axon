import pytest
from click.testing import CliRunner
from axon.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_agents_command(runner):
    result = runner.invoke(cli, ['agents'])
    assert result.exit_code == 0
    assert "Cursor" in result.output
    assert "Claude Code" in result.output
    assert "Gemini/Antigravity" in result.output

def test_list_command(runner):
    result = runner.invoke(cli, ['list', '--all'])
    assert result.exit_code == 0
    assert "All Staged Items" in result.output

def test_enable_disable_sync_linking(runner, tmp_path, monkeypatch):
    import axon.cli as cli_module
    import axon.core as core_module
    from axon.adapters import ADAPTERS, AgentAdapter
    from pathlib import Path

    # Stage a mock principle and mock skill
    mock_axon = tmp_path / ".axon"
    mock_principles = mock_axon / "principles"
    mock_skills = mock_axon / "skills"
    mock_principles.mkdir(parents=True)
    mock_skills.mkdir(parents=True)
    
    (mock_principles / "my-rule.md").write_text("rule content")
    (mock_skills / "my-skill.md").write_text("skill content")

    monkeypatch.setattr(cli_module, "AXON_DIR", mock_axon)
    monkeypatch.setattr(core_module, "AXON_DIR", mock_axon)
    monkeypatch.setattr(core_module, "CONFIG_FILE", mock_axon / "config.yaml")

    # Local target dirs
    local_agents_skills = tmp_path / ".agents" / "skills"
    local_agents_rules = tmp_path / ".agents" / "rules"
    local_agents_skills.mkdir(parents=True)
    local_agents_rules.mkdir(parents=True)

    # Global target dirs
    global_gemini_skills = tmp_path / "global_gemini" / "skills"
    global_gemini_rules = tmp_path / "global_gemini" / "rules"
    global_gemini_skills.mkdir(parents=True)
    global_gemini_rules.mkdir(parents=True)

    # Patch gemini adapter global paths for isolated testing
    test_adapters = {
        "gemini": AgentAdapter(
            name="Gemini/Antigravity",
            local_skill_dirs=[local_agents_skills],
            local_principle_dirs=[local_agents_rules],
            global_skill_dirs=[global_gemini_skills],
            global_principle_dirs=[global_gemini_rules]
        )
    }
    monkeypatch.setattr(cli_module, "ADAPTERS", test_adapters)
    monkeypatch.chdir(tmp_path)

    # --- 1. ENABLE LOCAL ---
    res_en_rule = runner.invoke(cli, ['enable', 'principle', 'my-rule.md'])
    assert res_en_rule.exit_code == 0
    assert (local_agents_rules / "my-rule.md").is_symlink()
    assert not (local_agents_skills / "my-rule.md").exists()

    res_en_skill = runner.invoke(cli, ['enable', 'skill', 'my-skill.md'])
    assert res_en_skill.exit_code == 0
    assert (local_agents_skills / "my-skill.md").is_symlink()
    assert not (local_agents_rules / "my-skill.md").exists()

    # --- 2. ENABLE GLOBAL ---
    res_en_glob_rule = runner.invoke(cli, ['enable', 'principle', 'my-rule.md', '--global'])
    assert res_en_glob_rule.exit_code == 0
    assert (global_gemini_rules / "my-rule.md").is_symlink()
    assert not (global_gemini_skills / "my-rule.md").exists()

    res_en_glob_skill = runner.invoke(cli, ['enable', 'skill', 'my-skill.md', '--global'])
    assert res_en_glob_skill.exit_code == 0
    assert (global_gemini_skills / "my-skill.md").is_symlink()
    assert not (global_gemini_rules / "my-skill.md").exists()

    # --- 3. DISABLE LOCAL & GLOBAL ---
    res_dis_rule = runner.invoke(cli, ['disable', 'principle', 'my-rule.md'])
    assert res_dis_rule.exit_code == 0
    assert not (local_agents_rules / "my-rule.md").exists()

    res_dis_skill = runner.invoke(cli, ['disable', 'skill', 'my-skill.md', '--global'])
    assert res_dis_skill.exit_code == 0
    assert not (global_gemini_skills / "my-skill.md").exists()

    # --- 4. SYNC ---
    # Delete remaining local skill symlink manually to test sync restoration
    if (local_agents_skills / "my-skill.md").exists():
        (local_agents_skills / "my-skill.md").unlink()

    res_sync = runner.invoke(cli, ['sync'], input='y\n')
    assert res_sync.exit_code == 0
    # Should restore local skill symlink because it's still enabled in config.yaml
    assert (local_agents_skills / "my-skill.md").is_symlink()
    # Should restore global principle symlink because it's still enabled in config.yaml
    assert (global_gemini_rules / "my-rule.md").is_symlink()
    # Confirm correct location separation after sync
    assert not (local_agents_rules / "my-skill.md").exists()
    assert not (global_gemini_skills / "my-rule.md").exists()

def test_dotfile_scaffolding_and_stale_cleanup(runner, tmp_path, monkeypatch):
    import axon.cli as cli_module
    import axon.core as core_module
    from axon.adapters import scaffold_local_env

    monkeypatch.chdir(tmp_path)

    # Initialize project for claude and cursor
    res_init = runner.invoke(cli, ['init', '--agent', 'claude', '--agent', 'cursor'])
    assert res_init.exit_code == 0
    assert (tmp_path / ".clauderc").is_file()
    assert not (tmp_path / ".clauderc").is_dir()
    assert (tmp_path / ".cursorrules").is_file()
    assert not (tmp_path / ".cursorrules").is_dir()

    # Simulate an old erroneous directory for .clauderc and run scaffold
    clauderc_path = tmp_path / ".clauderc"
    clauderc_path.unlink()
    clauderc_path.mkdir()
    assert clauderc_path.is_dir()

def test_auto_detection_and_list_principles(runner, tmp_path, monkeypatch):
    import axon.cli as cli_module
    import axon.core as core_module
    from axon.adapters import AgentAdapter

    mock_axon = tmp_path / ".axon"
    mock_principles = mock_axon / "principles"
    mock_principles.mkdir(parents=True)
    (mock_principles / "contract-first.md").write_text("contract first rule")

    monkeypatch.setattr(cli_module, "AXON_DIR", mock_axon)
    monkeypatch.setattr(core_module, "AXON_DIR", mock_axon)
    monkeypatch.setattr(core_module, "CONFIG_FILE", mock_axon / "config.yaml")

    agents_rules = tmp_path / ".agents" / "rules"
    agents_rules.mkdir(parents=True)

    test_adapters = {
        "gemini": AgentAdapter(
            name="Gemini/Antigravity",
            local_principle_dirs=[agents_rules]
        )
    }
    monkeypatch.setattr(cli_module, "ADAPTERS", test_adapters)
    monkeypatch.chdir(tmp_path)

    # 1. Enable without specifying 'principle' explicitly (auto-detection)
    res_enable = runner.invoke(cli, ['enable', 'contract-first.md'])
    assert res_enable.exit_code == 0
    assert (agents_rules / "contract-first.md").is_symlink()

    # 2. Check that 'axon list' displays Principles
    res_list = runner.invoke(cli, ['list'])
    assert res_list.exit_code == 0
    assert "Principles:" in res_list.output
    assert "contract-first.md" in res_list.output

    # 3. Disabling as a skill should NOT touch principles
    res_disable_skill = runner.invoke(cli, ['disable', 'skill', 'contract-first.md'])
    assert "Warning" in res_disable_skill.output or res_disable_skill.exit_code == 0
    assert (agents_rules / "contract-first.md").is_symlink()

    # 4. Disable without specifying item_type (auto-detection)
    res_disable_auto = runner.invoke(cli, ['disable', 'contract-first.md'])
    assert res_disable_auto.exit_code == 0
    assert not (agents_rules / "contract-first.md").exists()






