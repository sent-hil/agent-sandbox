"""Tests for utility functions."""

import tempfile
from pathlib import Path

import pytest

from agent_sandbox.utils import find_project_root, parse_compose_ports


class TestFindProjectRoot:
    """Tests for find_project_root function."""

    def test_finds_docker_compose_yml(self, tmp_path):
        """Should find project root with docker-compose.yml."""
        (tmp_path / "docker-compose.yml").write_text("services: {}")
        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)

        result = find_project_root(subdir)
        assert result == tmp_path

    def test_finds_docker_compose_yaml(self, tmp_path):
        """Should find project root with docker-compose.yaml."""
        (tmp_path / "docker-compose.yaml").write_text("services: {}")
        subdir = tmp_path / "src"
        subdir.mkdir()

        result = find_project_root(subdir)
        assert result == tmp_path

    def test_finds_compose_yml(self, tmp_path):
        """Should find project root with compose.yml."""
        (tmp_path / "compose.yml").write_text("services: {}")

        result = find_project_root(tmp_path)
        assert result == tmp_path

    def test_finds_compose_yaml(self, tmp_path):
        """Should find project root with compose.yaml."""
        (tmp_path / "compose.yaml").write_text("services: {}")

        result = find_project_root(tmp_path)
        assert result == tmp_path

    def test_returns_none_when_not_found(self, tmp_path):
        """Should return None when no compose file found."""
        subdir = tmp_path / "src"
        subdir.mkdir()

        result = find_project_root(subdir)
        assert result is None

    def test_stops_at_filesystem_root(self):
        """Should not infinite loop at filesystem root."""
        result = find_project_root(Path("/nonexistent/deep/path"))
        assert result is None


class TestParseComposePorts:
    """Tests for parse_compose_ports function."""

    def test_parses_simple_ports(self, tmp_path):
        """Should parse simple port mappings."""
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("""
services:
  dev:
    ports:
      - "8000:8000"
      - "5173:5173"
""")
        result = parse_compose_ports(compose, "dev")
        assert result == [8000, 5173]

    def test_parses_env_var_ports(self, tmp_path):
        """Should parse port mappings with environment variables."""
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("""
services:
  dev:
    ports:
      - "${SANDBOX_PORT_0:-8000}:8000"
      - "${SANDBOX_PORT_1:-5173}:5173"
""")
        result = parse_compose_ports(compose, "dev")
        assert result == [8000, 5173]

    def test_parses_host_port_only(self, tmp_path):
        """Should parse when only host port specified."""
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("""
services:
  dev:
    ports:
      - "8000"
""")
        result = parse_compose_ports(compose, "dev")
        assert result == [8000]

    def test_returns_empty_for_missing_service(self, tmp_path):
        """Should return empty list for missing service."""
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("""
services:
  web:
    ports:
      - "8000:8000"
""")
        result = parse_compose_ports(compose, "dev")
        assert result == []

    def test_returns_empty_for_no_ports(self, tmp_path):
        """Should return empty list when service has no ports."""
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("""
services:
  dev:
    build: .
""")
        result = parse_compose_ports(compose, "dev")
        assert result == []
