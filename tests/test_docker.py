"""Tests for Docker client."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_sandbox.docker import DockerClient


class TestDockerClient:
    """Tests for DockerClient class."""

    def test_init_with_compose_file(self, tmp_path):
        """Should initialize with compose file path."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        
        client = DockerClient(compose_file)
        assert client.compose_file == compose_file


class TestDockerClientContainerName:
    """Tests for container name handling."""

    def test_gets_container_name(self, tmp_path):
        """Should construct container name from project name."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            # Simulate no container exists, should return default hyphen format
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            
            result = client.container_name("alice", "dev")
            # Default is hyphen format when no container exists
            assert result == "alice-dev-1"

    def test_gets_container_name_underscore_format(self, tmp_path):
        """Should detect underscore format (podman-compose)."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            # First call (hyphen) returns empty, second call (underscore) returns match
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout=""),
                MagicMock(returncode=0, stdout="alice_dev_1\n"),
            ]
            
            result = client.container_name("alice", "dev")
            assert result == "alice_dev_1"


class TestDockerClientComposeUp:
    """Tests for compose_up method."""

    def test_compose_up_builds_correct_command(self, tmp_path):
        """Should build correct docker compose up command."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            client.compose_up(
                project_name="alice",
                service="dev",
                env={"SANDBOX_PORT_0": "8001"}
            )
            
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            env = call_args[1]["env"]
            
            assert "docker" in cmd
            assert "compose" in cmd
            assert "-p" in cmd
            assert "alice" in cmd
            assert "up" in cmd
            assert "-d" in cmd
            assert "dev" in cmd
            assert env["SANDBOX_PORT_0"] == "8001"

    def test_compose_up_raises_on_failure(self, tmp_path):
        """Should raise exception on compose failure."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error")
            
            with pytest.raises(RuntimeError):
                client.compose_up("alice", "dev", {})


class TestDockerClientComposeStop:
    """Tests for compose_stop method."""

    def test_compose_stop_builds_correct_command(self, tmp_path):
        """Should build correct docker compose stop command."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            client.compose_stop("alice", "dev")
            
            cmd = mock_run.call_args[0][0]
            assert "stop" in cmd
            assert "alice" in cmd


class TestDockerClientComposeRm:
    """Tests for compose_rm method."""

    def test_compose_rm_builds_correct_command(self, tmp_path):
        """Should build correct docker compose rm command."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            client.compose_rm("alice", "dev")
            
            cmd = mock_run.call_args[0][0]
            assert "rm" in cmd
            assert "-f" in cmd


class TestDockerClientListContainers:
    """Tests for list_sandbox_containers method."""

    def test_lists_containers(self, tmp_path):
        """Should list running sandbox containers."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="alice-dev-1\nbob-dev-1\n"
            )
            
            result = client.list_sandbox_containers()
            
            assert result == ["alice-dev-1", "bob-dev-1"]

    def test_returns_empty_on_no_containers(self, tmp_path):
        """Should return empty list when no containers."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            
            result = client.list_sandbox_containers()
            
            assert result == []


class TestDockerClientGetContainerPorts:
    """Tests for get_container_ports method."""

    def test_gets_container_ports(self, tmp_path):
        """Should get port mappings for a container."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="8000/tcp -> 0.0.0.0:8001\n5173/tcp -> 0.0.0.0:5174\n"
            )
            
            result = client.get_container_ports("alice-dev-1")
            
            assert result == {8000: 8001, 5173: 5174}

    def test_returns_empty_on_no_ports(self, tmp_path):
        """Should return empty dict when no port mappings."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            
            result = client.get_container_ports("alice-dev-1")
            
            assert result == {}


class TestDockerClientContainerExists:
    """Tests for container_exists method."""

    def test_container_exists_true(self, tmp_path):
        """Should return True when container exists."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="alice-dev-1\n"
            )
            
            result = client.container_exists("alice-dev-1")
            
            assert result is True

    def test_container_exists_false(self, tmp_path):
        """Should return False when container doesn't exist."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services: {}")
        client = DockerClient(compose_file)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            
            result = client.container_exists("alice-dev-1")
            
            assert result is False
