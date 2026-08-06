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
