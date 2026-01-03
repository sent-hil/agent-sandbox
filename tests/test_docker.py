"""Tests for Docker client."""

from unittest.mock import MagicMock, patch

import pytest

from agent_sandbox.docker import DockerClient


class TestDockerClient:
    """Tests for DockerClient class."""

    def test_init_with_project_root(self, tmp_path):
        """Should initialize with project root path."""
        client = DockerClient(tmp_path)
        assert client.project_root == tmp_path

    def test_container_name(self, tmp_path):
        """Should generate container name with sandbox prefix and namespace."""
        client = DockerClient(tmp_path)
        expected = f"sandbox-{client.namespace}-alice"
        assert client.container_name("alice") == expected

    def test_image_name(self, tmp_path):
        """Should generate image name with sandbox prefix and namespace."""
        client = DockerClient(tmp_path)
        expected = f"sandbox-{client.namespace}-alice:latest"
        assert client.image_name("alice") == expected


class TestDockerClientBuildImage:
    """Tests for build_image method."""

    def test_builds_image(self, tmp_path):
        """Should build image with correct command."""
        client = DockerClient(tmp_path)
        context = tmp_path / "context"
        context.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            client.build_image("alice", context, "Dockerfile")

            call_args = mock_run.call_args[0][0]
            assert "docker" in call_args
            assert "build" in call_args
            assert "-t" in call_args
            expected_image = f"sandbox-{client.namespace}-alice:latest"
            assert expected_image in call_args

    def test_raises_on_build_failure(self, tmp_path):
        """Should raise RuntimeError on build failure."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="build error")

            with pytest.raises(RuntimeError, match="docker build failed"):
                client.build_image("alice", tmp_path, "Dockerfile")


class TestDockerClientRunContainer:
    """Tests for run_container method."""

    def test_runs_container(self, tmp_path):
        """Should run container with correct command."""
        client = DockerClient(tmp_path)
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            client.run_container(
                sandbox_name="alice",
                image="sandbox-alice:latest",
                workspace_path=workspace,
                workdir="/workspaces/project",
                ports={8000: 8001, 5173: 5174},
            )

            call_args = mock_run.call_args[0][0]
            assert "docker" in call_args
            assert "run" in call_args
            assert "-d" in call_args
            assert "--name" in call_args
            expected_container = f"sandbox-{client.namespace}-alice"
            assert expected_container in call_args
            assert "--label" in call_args

    def test_raises_on_run_failure(self, tmp_path):
        """Should raise RuntimeError on run failure."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="run error")

            with pytest.raises(RuntimeError, match="docker run failed"):
                client.run_container(
                    sandbox_name="alice",
                    image="test:latest",
                    workspace_path=tmp_path,
                    workdir="/app",
                    ports={},
                )


class TestDockerClientContainerExists:
    """Tests for container_exists method."""

    def test_returns_true_when_exists(self, tmp_path):
        """Should return True when container is running."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            expected_container = f"sandbox-{client.namespace}-alice"
            mock_run.return_value = MagicMock(
                returncode=0, stdout=f"{expected_container}\n"
            )

            result = client.container_exists("alice")
            assert result is True

    def test_returns_false_when_not_exists(self, tmp_path):
        """Should return False when container not running."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")

            result = client.container_exists("alice")
            assert result is False


class TestDockerClientListContainers:
    """Tests for list_sandbox_containers method."""

    def test_lists_containers(self, tmp_path):
        """Should list running sandbox containers."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="sandbox-alice\nsandbox-bob\n"
            )

            result = client.list_sandbox_containers()
            assert result == ["sandbox-alice", "sandbox-bob"]

    def test_returns_empty_on_no_containers(self, tmp_path):
        """Should return empty list when no containers."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")

            result = client.list_sandbox_containers()
            assert result == []


class TestDockerClientGetContainerPorts:
    """Tests for get_container_ports method."""

    def test_gets_container_ports(self, tmp_path):
        """Should get port mappings for a container."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="8000/tcp -> 0.0.0.0:8001\n5173/tcp -> 0.0.0.0:5174\n",
            )

            result = client.get_container_ports("alice")
            assert result == {8000: 8001, 5173: 5174}

    def test_returns_empty_on_no_ports(self, tmp_path):
        """Should return empty dict when no port mappings."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")

            result = client.get_container_ports("alice")
            assert result == {}


class TestDockerClientStopContainer:
    """Tests for stop_container method."""

    def test_stops_container(self, tmp_path):
        """Should stop container."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            client.stop_container("alice")

            call_args = mock_run.call_args[0][0]
            assert "docker" in call_args
            assert "stop" in call_args
            expected_container = f"sandbox-{client.namespace}-alice"
            assert expected_container in call_args


class TestDockerClientRemoveContainer:
    """Tests for remove_container method."""

    def test_removes_container(self, tmp_path):
        """Should remove container."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            client.remove_container("alice")

            call_args = mock_run.call_args[0][0]
            assert "docker" in call_args
            assert "rm" in call_args
            assert "-f" in call_args
            expected_container = f"sandbox-{client.namespace}-alice"
            assert expected_container in call_args


class TestDockerClientGetSandboxName:
    """Tests for get_sandbox_name_from_container method."""

    def test_extracts_name(self, tmp_path):
        """Should extract sandbox name from container name."""
        client = DockerClient(tmp_path)

        result = client.get_sandbox_name_from_container("sandbox-alice")
        assert result == "alice"

    def test_handles_no_prefix(self, tmp_path):
        """Should return as-is if no prefix."""
        client = DockerClient(tmp_path)

        result = client.get_sandbox_name_from_container("alice")
        assert result == "alice"


class TestDockerClientShellExists:
    """Tests for DockerClient.shell_exists method."""

    def test_returns_true_when_shell_exists(self, tmp_path):
        """Should return True when shell exists in container."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = client.shell_exists("alice", "/bin/bash")

            assert result is True
            call_args = mock_run.call_args[0][0]
            expected_container = f"sandbox-{client.namespace}-alice"
            assert call_args == [
                "docker",
                "exec",
                expected_container,
                "test",
                "-x",
                "/bin/bash",
            ]

    def test_returns_false_when_shell_not_exists(self, tmp_path):
        """Should return False when shell doesn't exist in container."""
        client = DockerClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = client.shell_exists("alice", "/usr/bin/fish")

            assert result is False


class TestDockerClientExecShell:
    """Tests for DockerClient.exec_shell method."""

    def test_raises_when_shell_not_exists(self, tmp_path):
        """Should raise RuntimeError when shell doesn't exist."""
        client = DockerClient(tmp_path)

        with patch.object(client, "shell_exists", return_value=False):
            with pytest.raises(RuntimeError) as exc_info:
                client.exec_shell("alice", "/usr/bin/fish")

            assert "not found in container" in str(exc_info.value)
            assert "agent-sandbox rm alice" in str(exc_info.value)
