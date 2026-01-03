"""Tests for config management."""

from pathlib import Path

from agent_sandbox.config import (
    get_config_path,
    get_default_shell,
    get_git_email,
    get_git_name,
    load_user_config,
)


class TestGetConfigPath:
    """Tests for get_config_path function."""

    def test_returns_home_config_path(self):
        """Should return ~/.agent-sandbox.toml."""
        result = get_config_path()
        assert result == Path.home() / ".agent-sandbox.toml"


class TestLoadUserConfig:
    """Tests for load_user_config function."""

    def test_loads_valid_config(self, tmp_path, mocker):
        """Should load valid TOML config."""
        config_file = tmp_path / ".agent-sandbox.toml"
        config_file.write_text('shell = "/usr/bin/fish"\n')

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = load_user_config()
        assert result == {"shell": "/usr/bin/fish"}

    def test_returns_empty_when_file_not_exists(self, tmp_path, mocker):
        """Should return empty dict when config file doesn't exist."""
        config_file = tmp_path / ".agent-sandbox.toml"

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = load_user_config()
        assert result == {}

    def test_returns_empty_on_invalid_toml(self, tmp_path, mocker):
        """Should return empty dict on invalid TOML."""
        config_file = tmp_path / ".agent-sandbox.toml"
        config_file.write_text("invalid toml content [[[")

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = load_user_config()
        assert result == {}


class TestGetDefaultShell:
    """Tests for get_default_shell function."""

    def test_gets_shell_from_config(self, tmp_path, mocker):
        """Should get shell from config file."""
        config_file = tmp_path / ".agent-sandbox.toml"
        config_file.write_text('shell = "/usr/bin/fish"\n')

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = get_default_shell()
        assert result == "/usr/bin/fish"

    def test_returns_none_when_not_configured(self, tmp_path, mocker):
        """Should return None when shell not in config."""
        config_file = tmp_path / ".agent-sandbox.toml"
        config_file.write_text('other_setting = "value"\n')

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = get_default_shell()
        assert result is None

    def test_returns_none_when_file_not_exists(self, tmp_path, mocker):
        """Should return None when config file doesn't exist."""
        config_file = tmp_path / ".agent-sandbox.toml"

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = get_default_shell()
        assert result is None


class TestGetGitName:
    """Tests for get_git_name function."""

    def test_gets_name_from_config(self, tmp_path, mocker):
        """Should get git name from config file."""
        config_file = tmp_path / ".agent-sandbox.toml"
        config_file.write_text('[git]\nname = "John Doe"\n')

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = get_git_name()
        assert result == "John Doe"

    def test_returns_none_when_not_configured(self, tmp_path, mocker):
        """Should return None when git name not in config."""
        config_file = tmp_path / ".agent-sandbox.toml"
        config_file.write_text('[git]\nemail = "john@example.com"\n')

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = get_git_name()
        assert result is None

    def test_returns_none_when_file_not_exists(self, tmp_path, mocker):
        """Should return None when config file doesn't exist."""
        config_file = tmp_path / ".agent-sandbox.toml"

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = get_git_name()
        assert result is None


class TestGetGitEmail:
    """Tests for get_git_email function."""

    def test_gets_email_from_config(self, tmp_path, mocker):
        """Should get git email from config file."""
        config_file = tmp_path / ".agent-sandbox.toml"
        config_file.write_text('[git]\nemail = "john@example.com"\n')

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = get_git_email()
        assert result == "john@example.com"

    def test_returns_none_when_not_configured(self, tmp_path, mocker):
        """Should return None when git email not in config."""
        config_file = tmp_path / ".agent-sandbox.toml"
        config_file.write_text('[git]\nname = "John Doe"\n')

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = get_git_email()
        assert result is None

    def test_returns_none_when_file_not_exists(self, tmp_path, mocker):
        """Should return None when config file doesn't exist."""
        config_file = tmp_path / ".agent-sandbox.toml"

        mocker.patch("agent_sandbox.config.get_config_path", return_value=config_file)

        result = get_git_email()
        assert result is None
