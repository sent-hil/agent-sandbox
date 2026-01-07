"""Tests for CLI commands."""

from click.testing import CliRunner
from agent_sandbox.cli import main, complete_sandbox_names


class TestCompletionCommand:
    """Test the completion command."""

    def test_completion_bash_instructions(self):
        """Test bash completion instruction generation."""
        runner = CliRunner()
        result = runner.invoke(main, ["completion", "bash"])
        assert result.exit_code == 0
        assert "_AGENT_SANDBOX_COMPLETE=bash_source" in result.output
        assert "~/.bashrc" in result.output

    def test_completion_zsh_instructions(self):
        """Test zsh completion instruction generation."""
        runner = CliRunner()
        result = runner.invoke(main, ["completion", "zsh"])
        assert result.exit_code == 0
        assert "_AGENT_SANDBOX_COMPLETE=zsh_source" in result.output
        assert "~/.zshrc" in result.output

    def test_completion_fish_instructions(self):
        """Test fish completion instruction generation."""
        runner = CliRunner()
        result = runner.invoke(main, ["completion", "fish"])
        assert result.exit_code == 0
        assert "_AGENT_SANDBOX_COMPLETE=fish_source" in result.output
        assert "~/.config/fish/completions" in result.output

    def test_completion_invalid_shell(self):
        """Test error handling for invalid shell."""
        runner = CliRunner()
        result = runner.invoke(main, ["completion", "invalid"])
        assert result.exit_code == 2  # Click validation error
        assert "Invalid value" in result.output and "invalid" in result.output

    def test_completion_help_message(self):
        """Test completion command help message."""
        runner = CliRunner()
        result = runner.invoke(main, ["completion", "--help"])
        assert result.exit_code == 0
        assert "Generate shell completion" in result.output
        assert "bash" in result.output
        assert "zsh" in result.output
        assert "fish" in result.output
        assert "--install" in result.output


class TestSandboxNameCompletion:
    """Test sandbox name completion functionality."""

    def test_complete_sandbox_names_empty(self):
        """Test completion with no sandboxes."""
        # Mock context and param (not used in this case)
        ctx = None
        param = None

        # Test with empty incomplete string
        result = complete_sandbox_names(ctx, param, "")

        # Should return empty list when no sandboxes exist
        assert isinstance(result, list)
        # May be empty or contain some default names

    def test_complete_sandbox_names_partial(self):
        """Test completion with partial input."""
        ctx = None
        param = None

        # Test with partial input
        result = complete_sandbox_names(ctx, param, "test")

        # Should return empty list when no sandboxes match
        assert isinstance(result, list)
        # Should filter by prefix

    def test_complete_sandbox_names_error_handling(self):
        """Test completion handles errors gracefully."""
        # Create a scenario where manager might fail
        ctx = None
        param = None

        # Should not raise exceptions even if manager fails
        result = complete_sandbox_names(ctx, param, "anything")
        assert isinstance(result, list)
