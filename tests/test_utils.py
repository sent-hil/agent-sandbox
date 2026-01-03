"""Tests for utility functions."""

import json
from pathlib import Path


from agent_sandbox.utils import (
    find_project_root,
    find_devcontainer_json,
    parse_devcontainer_json,
    parse_devcontainer_ports,
    get_devcontainer_build_context,
    get_devcontainer_image,
    get_devcontainer_workdir,
    extract_sandbox_name,
)


class TestFindProjectRoot:
    """Tests for find_project_root function."""

    def test_finds_devcontainer_in_subdir(self, tmp_path):
        """Should find project root with .devcontainer/devcontainer.json."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "devcontainer.json").write_text("{}")

        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)

        result = find_project_root(subdir)
        assert result == tmp_path

    def test_finds_devcontainer_at_root(self, tmp_path):
        """Should find project root with .devcontainer.json at root."""
        (tmp_path / ".devcontainer.json").write_text("{}")

        result = find_project_root(tmp_path)
        assert result == tmp_path

    def test_prefers_subdir_devcontainer(self, tmp_path):
        """Should find .devcontainer/ before .devcontainer.json."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "devcontainer.json").write_text('{"name": "subdir"}')
        (tmp_path / ".devcontainer.json").write_text('{"name": "root"}')

        result = find_project_root(tmp_path)
        assert result == tmp_path

    def test_returns_none_when_not_found(self, tmp_path):
        """Should return None when no devcontainer.json found."""
        subdir = tmp_path / "src"
        subdir.mkdir()

        result = find_project_root(subdir)
        assert result is None

    def test_stops_at_filesystem_root(self):
        """Should not infinite loop at filesystem root."""
        result = find_project_root(Path("/nonexistent/deep/path"))
        assert result is None


class TestFindDevcontainerJson:
    """Tests for find_devcontainer_json function."""

    def test_finds_in_subdir(self, tmp_path):
        """Should find devcontainer.json in .devcontainer/ subdir."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        expected = devcontainer_dir / "devcontainer.json"
        expected.write_text("{}")

        result = find_devcontainer_json(tmp_path)
        assert result == expected

    def test_finds_at_root(self, tmp_path):
        """Should find .devcontainer.json at root."""
        expected = tmp_path / ".devcontainer.json"
        expected.write_text("{}")

        result = find_devcontainer_json(tmp_path)
        assert result == expected

    def test_returns_none_when_not_found(self, tmp_path):
        """Should return None when not found."""
        result = find_devcontainer_json(tmp_path)
        assert result is None


class TestParseDevcontainerJson:
    """Tests for parse_devcontainer_json function."""

    def test_parses_valid_json(self, tmp_path):
        """Should parse valid JSON."""
        devcontainer = tmp_path / "devcontainer.json"
        devcontainer.write_text('{"name": "test", "forwardPorts": [8000]}')

        result = parse_devcontainer_json(devcontainer)
        assert result == {"name": "test", "forwardPorts": [8000]}

    def test_strips_single_line_comments(self, tmp_path):
        """Should handle JSON with single-line comments."""
        devcontainer = tmp_path / "devcontainer.json"
        devcontainer.write_text("""
{
    // This is a comment
    "name": "test"
}
""")
        result = parse_devcontainer_json(devcontainer)
        assert result == {"name": "test"}

    def test_strips_multi_line_comments(self, tmp_path):
        """Should handle JSON with multi-line comments."""
        devcontainer = tmp_path / "devcontainer.json"
        devcontainer.write_text("""
{
    /* This is a
       multi-line comment */
    "name": "test"
}
""")
        result = parse_devcontainer_json(devcontainer)
        assert result == {"name": "test"}

    def test_returns_empty_on_invalid_json(self, tmp_path):
        """Should return empty dict on invalid JSON."""
        devcontainer = tmp_path / "devcontainer.json"
        devcontainer.write_text("not valid json")

        result = parse_devcontainer_json(devcontainer)
        assert result == {}


class TestParseDevcontainerPorts:
    """Tests for parse_devcontainer_ports function."""

    def test_parses_integer_ports(self, tmp_path):
        """Should parse integer ports from forwardPorts."""
        devcontainer = tmp_path / "devcontainer.json"
        devcontainer.write_text('{"forwardPorts": [8000, 5173, 3000]}')

        result = parse_devcontainer_ports(devcontainer)
        assert result == [8000, 5173, 3000]

    def test_parses_string_ports(self, tmp_path):
        """Should parse string ports from forwardPorts."""
        devcontainer = tmp_path / "devcontainer.json"
        devcontainer.write_text('{"forwardPorts": ["8000", "5173"]}')

        result = parse_devcontainer_ports(devcontainer)
        assert result == [8000, 5173]

    def test_returns_empty_for_missing_ports(self, tmp_path):
        """Should return empty list when forwardPorts not present."""
        devcontainer = tmp_path / "devcontainer.json"
        devcontainer.write_text('{"name": "test"}')

        result = parse_devcontainer_ports(devcontainer)
        assert result == []


class TestGetDevcontainerBuildContext:
    """Tests for get_devcontainer_build_context function."""

    def test_gets_build_config(self, tmp_path):
        """Should get build context and dockerfile from build config."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text(
            json.dumps({"build": {"context": "..", "dockerfile": "Dockerfile.dev"}})
        )

        context, dockerfile = get_devcontainer_build_context(devcontainer)
        assert context == tmp_path
        assert dockerfile == "Dockerfile.dev"

    def test_gets_legacy_dockerfile(self, tmp_path):
        """Should get legacy dockerFile property."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"dockerFile": "Dockerfile"}')

        context, dockerfile = get_devcontainer_build_context(devcontainer)
        assert context == devcontainer_dir
        assert dockerfile == "Dockerfile"

    def test_finds_default_dockerfile(self, tmp_path):
        """Should find Dockerfile in .devcontainer/ by default."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"name": "test"}')
        (devcontainer_dir / "Dockerfile").write_text("FROM alpine")

        context, dockerfile = get_devcontainer_build_context(devcontainer)
        assert context == devcontainer_dir
        assert dockerfile == "Dockerfile"

    def test_returns_empty_for_image_only(self, tmp_path):
        """Should return empty dockerfile for image-only config."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"image": "python:3.12"}')

        context, dockerfile = get_devcontainer_build_context(devcontainer)
        assert dockerfile == ""


class TestGetDevcontainerImage:
    """Tests for get_devcontainer_image function."""

    def test_gets_image(self, tmp_path):
        """Should get image from config."""
        devcontainer = tmp_path / "devcontainer.json"
        devcontainer.write_text('{"image": "python:3.12-slim"}')

        result = get_devcontainer_image(devcontainer)
        assert result == "python:3.12-slim"

    def test_returns_none_for_build(self, tmp_path):
        """Should return None when build config is used."""
        devcontainer = tmp_path / "devcontainer.json"
        devcontainer.write_text('{"build": {"dockerfile": "Dockerfile"}}')

        result = get_devcontainer_image(devcontainer)
        assert result is None


class TestGetDevcontainerWorkdir:
    """Tests for get_devcontainer_workdir function."""

    def test_gets_workspace_folder(self, tmp_path):
        """Should get workspaceFolder from config."""
        devcontainer = tmp_path / "devcontainer.json"
        devcontainer.write_text('{"workspaceFolder": "/app"}')

        result = get_devcontainer_workdir(devcontainer)
        assert result == "/app"

    def test_returns_default(self, tmp_path):
        """Should return default when workspaceFolder not set."""
        devcontainer = tmp_path / "devcontainer.json"
        devcontainer.write_text('{"name": "test"}')

        result = get_devcontainer_workdir(devcontainer)
        assert result == "/workspaces/project"


class TestExtractSandboxName:
    """Tests for extract_sandbox_name function."""

    def test_extracts_name(self):
        """Should extract sandbox name from container name."""
        result = extract_sandbox_name("sandbox-alice")
        assert result == "alice"

    def test_handles_no_prefix(self):
        """Should return as-is if no sandbox- prefix."""
        result = extract_sandbox_name("alice")
        assert result == "alice"
