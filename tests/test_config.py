"""Tests for config management."""

from pathlib import Path

from agent_sandbox.config import (
    find_project_config,
    get_default_shell,
    get_user_config_path,
    load_config,
    load_config_file,
)


class TestGetUserConfigPath:
    """Tests for get_user_config_path function."""

    def test_returns_home_config_path(self):
        """Should return ~/.agent-sandbox.toml."""
        result = get_user_config_path()
        assert result == Path.home() / ".agent-sandbox.toml"


class TestFindProjectConfig:
    """Tests for find_project_config function."""

    def test_finds_config_in_current_dir(self, tmp_path, monkeypatch):
        """Should find agent-sandbox.toml in current directory."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[defaults]\nshell = "/bin/bash"\n')

        monkeypatch.chdir(tmp_path)

        result = find_project_config()
        assert result == config_file

    def test_finds_dotfile_config(self, tmp_path, monkeypatch):
        """Should find .agent-sandbox.toml in current directory."""
        config_file = tmp_path / ".agent-sandbox.toml"
        config_file.write_text('[defaults]\nshell = "/bin/bash"\n')

        monkeypatch.chdir(tmp_path)

        result = find_project_config()
        assert result == config_file

    def test_prefers_non_dotfile(self, tmp_path, monkeypatch):
        """Should prefer agent-sandbox.toml over .agent-sandbox.toml."""
        (tmp_path / "agent-sandbox.toml").write_text('shell = "preferred"\n')
        (tmp_path / ".agent-sandbox.toml").write_text('shell = "dotfile"\n')

        monkeypatch.chdir(tmp_path)

        result = find_project_config()
        assert result == tmp_path / "agent-sandbox.toml"

    def test_finds_config_in_parent_dir(self, tmp_path, monkeypatch):
        """Should find config in parent directory."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[defaults]\nshell = "/bin/bash"\n')

        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)

        monkeypatch.chdir(subdir)

        result = find_project_config()
        assert result == config_file

    def test_returns_none_when_not_found(self, tmp_path, monkeypatch):
        """Should return None when no config file exists."""
        monkeypatch.chdir(tmp_path)

        result = find_project_config()
        assert result is None


class TestLoadConfigFile:
    """Tests for load_config_file function."""

    def test_loads_valid_config(self, tmp_path):
        """Should load valid TOML config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('shell = "/usr/bin/fish"\n')

        result = load_config_file(config_file)
        assert result == {"shell": "/usr/bin/fish"}

    def test_returns_empty_on_invalid_toml(self, tmp_path):
        """Should return empty dict on invalid TOML."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("invalid toml content [[[")

        result = load_config_file(config_file)
        assert result == {}


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_project_config(self, tmp_path, monkeypatch):
        """Should load project config."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[defaults]\nshell = "/usr/bin/fish"\n')

        monkeypatch.chdir(tmp_path)

        result = load_config()
        assert result == {"defaults": {"shell": "/usr/bin/fish"}}

    def test_project_config_overrides_user_config(self, tmp_path, monkeypatch):
        """Should prefer project config over user config."""
        # Create user config
        user_config = tmp_path / "home" / ".agent-sandbox.toml"
        user_config.parent.mkdir()
        user_config.write_text('shell = "/bin/bash"\nuser_only = "value"\n')

        # Create project config
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config = project_dir / "agent-sandbox.toml"
        project_config.write_text('shell = "/usr/bin/fish"\n')

        monkeypatch.chdir(project_dir)
        monkeypatch.setattr(
            "agent_sandbox.config.get_user_config_path", lambda: user_config
        )

        result = load_config()
        # Project shell overrides user shell
        assert result["shell"] == "/usr/bin/fish"
        # User-only settings are preserved
        assert result["user_only"] == "value"


class TestGetDefaultShell:
    """Tests for get_default_shell function."""

    def test_gets_shell_from_sandbox_section(self, tmp_path, monkeypatch):
        """Should get shell from [sandbox].default_shell."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[sandbox]\ndefault_shell = "/usr/bin/fish"\n')

        monkeypatch.chdir(tmp_path)

        result = get_default_shell()
        assert result == "/usr/bin/fish"

    def test_gets_shell_from_defaults_section(self, tmp_path, monkeypatch):
        """Should get shell from [defaults].shell."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[defaults]\nshell = "/usr/bin/fish"\n')

        monkeypatch.chdir(tmp_path)

        result = get_default_shell()
        assert result == "/usr/bin/fish"

    def test_gets_shell_from_top_level(self, tmp_path, monkeypatch):
        """Should get shell from top-level 'shell'."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('shell = "/usr/bin/fish"\n')

        monkeypatch.chdir(tmp_path)

        result = get_default_shell()
        assert result == "/usr/bin/fish"

    def test_sandbox_section_takes_priority(self, tmp_path, monkeypatch):
        """Should prefer [sandbox].default_shell over other locations."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text(
            '[sandbox]\ndefault_shell = "/usr/bin/zsh"\n\n'
            '[defaults]\nshell = "/usr/bin/fish"\n'
        )

        monkeypatch.chdir(tmp_path)

        result = get_default_shell()
        assert result == "/usr/bin/zsh"

    def test_defaults_section_takes_priority_over_top_level(self, tmp_path, monkeypatch):
        """Should prefer [defaults].shell over top-level shell."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text(
            'shell = "/bin/bash"\n\n'
            '[defaults]\nshell = "/usr/bin/fish"\n'
        )

        monkeypatch.chdir(tmp_path)

        result = get_default_shell()
        assert result == "/usr/bin/fish"

    def test_returns_none_when_not_configured(self, tmp_path, monkeypatch):
        """Should return None when shell not in config."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('other_setting = "value"\n')

        monkeypatch.chdir(tmp_path)

        result = get_default_shell()
        assert result is None

    def test_returns_none_when_no_config(self, tmp_path, monkeypatch):
        """Should return None when no config file exists."""
        monkeypatch.chdir(tmp_path)
        # Also mock user config to not exist
        monkeypatch.setattr(
            "agent_sandbox.config.get_user_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )

        result = get_default_shell()
        assert result is None
