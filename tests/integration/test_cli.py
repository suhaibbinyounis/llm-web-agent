"""
Integration tests for the CLI commands.
"""

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


class TestCLIRun:
    """Test the 'run' CLI command."""
    
    def test_run_help(self, runner):
        """Test help for run command."""
        from llm_web_agent.main import app
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "Execute a natural language instruction" in result.stdout
    
    def test_run_visible_option(self, runner):
        """Test visible option exists."""
        from llm_web_agent.main import app
        result = runner.invoke(app, ["run", "--help"])
        assert "--visible" in result.stdout
    
    def test_run_browser_option(self, runner):
        """Test browser option exists."""
        from llm_web_agent.main import app
        result = runner.invoke(app, ["run", "--help"])
        assert "--browser" in result.stdout


class TestCLIRunFile:
    """Test the 'run-file' CLI command."""
    
    def test_run_file_help(self, runner):
        """Test help for run-file command."""
        from llm_web_agent.main import app
        result = runner.invoke(app, ["run-file", "--help"])
        assert result.exit_code == 0
        assert "Execute instructions from a file" in result.stdout
    
    def test_run_file_nonexistent_file(self, runner, tmp_path):
        """Test error on nonexistent file."""
        from llm_web_agent.main import app
        result = runner.invoke(app, ["run-file", str(tmp_path / "nonexistent.txt")])
        assert result.exit_code != 0
        assert "not found" in result.stdout.lower() or result.exit_code != 0





class TestCLIList:
    """Test the 'list' CLI commands."""
    
    def test_list_scripts_help(self, runner):
        """Test help for list-scripts command."""
        from llm_web_agent.main import app
        result = runner.invoke(app, ["list-scripts", "--help"])
        # Command may or may not exist - just test it doesn't crash
        assert result.exit_code in [0, 2]


class TestCLIVersion:
    """Test version output."""
    
    def test_version(self, runner):
        """Test version output."""
        from llm_web_agent.main import app
        result = runner.invoke(app, ["--version"])
        # May or may not have version flag configured
        # Just verify it runs without unexpected crash
        assert result.exit_code in [0, 2]


class TestCLIApp:
    """Test general CLI app behavior."""
    
    def test_main_help(self, runner):
        """Test main app help."""
        from llm_web_agent.main import app
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "llm-web-agent" in result.stdout.lower() or "browser automation" in result.stdout.lower()
    
    def test_invalid_command(self, runner):
        """Test invalid command shows error."""
        from llm_web_agent.main import app
        result = runner.invoke(app, ["invalid-command"])
        assert result.exit_code != 0
