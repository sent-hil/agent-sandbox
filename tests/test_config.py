"""Tests for config management."""

from pathlib import Path

from agent_sandbox.config import (
    find_project_config,
    get_default_shell,
    get_git_email,
    get_git_name,
    get_mounts,
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

    def test_defaults_section_takes_priority_over_top_level(
        self, tmp_path, monkeypatch
    ):
        """Should prefer [defaults].shell over top-level shell."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text(
            'shell = "/bin/bash"\n\n[defaults]\nshell = "/usr/bin/fish"\n'
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


class TestGetGitName:
    """Tests for get_git_name function."""

    def test_gets_name_from_config(self, tmp_path, monkeypatch):
        """Should get git name from config file."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[git]\nname = "John Doe"\n')

        monkeypatch.chdir(tmp_path)

        result = get_git_name()
        assert result == "John Doe"

    def test_returns_none_when_not_configured(self, tmp_path, monkeypatch):
        """Should return None when git name not in config."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[git]\nemail = "john@example.com"\n')

        monkeypatch.chdir(tmp_path)

        result = get_git_name()
        assert result is None

    def test_returns_none_when_file_not_exists(self, tmp_path, monkeypatch):
        """Should return None when config file doesn't exist."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "agent_sandbox.config.get_user_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )

        result = get_git_name()
        assert result is None


class TestGetGitEmail:
    """Tests for get_git_email function."""

    def test_gets_email_from_config(self, tmp_path, monkeypatch):
        """Should get git email from config file."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[git]\nemail = "john@example.com"\n')

        monkeypatch.chdir(tmp_path)

        result = get_git_email()
        assert result == "john@example.com"

    def test_returns_none_when_not_configured(self, tmp_path, monkeypatch):
        """Should return None when git email not in config."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[git]\nname = "John Doe"\n')

        monkeypatch.chdir(tmp_path)

        result = get_git_email()
        assert result is None

    def test_returns_none_when_file_not_exists(self, tmp_path, monkeypatch):
        """Should return None when config file doesn't exist."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "agent_sandbox.config.get_user_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )

        result = get_git_email()
        assert result is None


class TestGetMounts:
    """Tests for get_mounts function."""

    def test_gets_mounts_from_config(self, tmp_path, monkeypatch):
        """Should get mounts from config file."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[files]\nmounts = ["/host/path:/container/path"]\n')

        monkeypatch.chdir(tmp_path)

        result = get_mounts()
        assert result == [("/host/path", "/container/path")]

    def test_expands_tilde_in_source(self, tmp_path, monkeypatch):
        """Should expand ~ in source path."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text(
            '[files]\nmounts = ["~/.config/app:/root/.config/app"]\n'
        )

        monkeypatch.chdir(tmp_path)

        result = get_mounts()
        assert len(result) == 1
        source, dest = result[0]
        assert source.startswith(str(Path.home()))
        assert source.endswith(".config/app")
        assert dest == "/root/.config/app"

    def test_handles_multiple_mounts(self, tmp_path, monkeypatch):
        """Should handle multiple mount entries."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text(
            '[files]\nmounts = [\n    "/path1:/dest1",\n    "/path2:/dest2"\n]\n'
        )

        monkeypatch.chdir(tmp_path)

        result = get_mounts()
        assert result == [("/path1", "/dest1"), ("/path2", "/dest2")]

    def test_returns_empty_when_not_configured(self, tmp_path, monkeypatch):
        """Should return empty list when mounts not in config."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[files]\nother = "value"\n')

        monkeypatch.chdir(tmp_path)

        result = get_mounts()
        assert result == []

    def test_returns_empty_when_no_files_section(self, tmp_path, monkeypatch):
        """Should return empty list when no files section."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text('[git]\nname = "John"\n')

        monkeypatch.chdir(tmp_path)

        result = get_mounts()
        assert result == []

    def test_skips_invalid_entries(self, tmp_path, monkeypatch):
        """Should skip entries without colon separator."""
        config_file = tmp_path / "agent-sandbox.toml"
        config_file.write_text(
            "[files]\nmounts = [\n"
            '    "/valid:/dest",\n'
            '    "invalid-no-colon",\n'
            "    123\n"
            "]\n"
        )

        monkeypatch.chdir(tmp_path)

        result = get_mounts()
        assert result == [("/valid", "/dest")]
