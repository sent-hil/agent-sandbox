"""Tests for SandboxManager."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_sandbox.manager import SandboxManager, SandboxInfo


class TestSandboxManager:
    """Tests for SandboxManager class."""

    def test_init_with_project_root(self, tmp_path):
        """Should initialize with project root."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services:\n  dev:\n    ports:\n      - '8000:8000'")
        
        manager = SandboxManager(tmp_path)
        assert manager.project_root == tmp_path

    def test_init_auto_detects_project_root(self, tmp_path):
        """Should auto-detect project root from subdirectory."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services:\n  dev:\n    ports:\n      - '8000:8000'")
        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)
        
        with patch("agent_sandbox.manager.find_project_root", return_value=tmp_path):
            manager = SandboxManager(subdir)
            assert manager.project_root == tmp_path

    def test_init_raises_when_no_project_root(self, tmp_path):
        """Should raise when no project root found."""
        with patch("agent_sandbox.manager.find_project_root", return_value=None):
            with pytest.raises(ValueError, match="Could not find"):
                SandboxManager(tmp_path)


class TestSandboxManagerPortCalculation:
    """Tests for port offset calculation."""

    def test_calculates_next_port_offset_empty(self, tmp_path):
        """Should return 0 when no sandboxes running."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services:\n  dev:\n    ports:\n      - '8000:8000'")
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.list_sandbox_containers.return_value = []
        
        offset = manager._get_next_port_offset()
        assert offset == 0

    def test_calculates_next_port_offset_with_existing(self, tmp_path):
        """Should return next offset based on existing containers."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services:\n  dev:\n    ports:\n      - '8000:8000'")
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.list_sandbox_containers.return_value = ["alice-dev-1", "bob-dev-1"]
        manager._docker.get_container_ports.side_effect = [
            {8000: 8000},  # alice has offset 0
            {8000: 8001},  # bob has offset 1
        ]
        manager._base_ports = [8000]
        
        offset = manager._get_next_port_offset()
        assert offset == 2


class TestSandboxManagerStart:
    """Tests for start method."""

    def test_start_creates_worktree_and_container(self, tmp_path):
        """Should create worktree and start container."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services:\n  dev:\n    ports:\n      - '8000:8000'")
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.list_sandbox_containers.return_value = []
        manager._docker.container_exists.return_value = False
        manager._git = MagicMock()
        manager._git.create_worktree.return_value = tmp_path / ".worktrees" / "alice"
        manager._git.get_current_branch.return_value = "sandbox/alice"
        manager._base_ports = [8000]
        
        result = manager.start("alice")
        
        assert result.name == "alice"
        assert result.ports == {8000: 8000}
        manager._git.create_worktree.assert_called_once_with("alice", None)
        manager._docker.compose_up.assert_called_once()

    def test_start_skips_if_already_running(self, tmp_path):
        """Should skip start if sandbox already running."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services:\n  dev:\n    ports:\n      - '8000:8000'")
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.container_exists.return_value = True
        manager._docker.get_container_ports.return_value = {8000: 8001}
        manager._git = MagicMock()
        manager._git.get_current_branch.return_value = "sandbox/alice"
        
        result = manager.start("alice")
        
        # Should not call compose_up since already running
        manager._docker.compose_up.assert_not_called()
        assert result.name == "alice"

    def test_start_with_custom_branch(self, tmp_path):
        """Should use custom branch when specified."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services:\n  dev:\n    ports:\n      - '8000:8000'")
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.list_sandbox_containers.return_value = []
        manager._docker.container_exists.return_value = False
        manager._git = MagicMock()
        manager._git.create_worktree.return_value = tmp_path / ".worktrees" / "alice"
        manager._git.get_current_branch.return_value = "feature/login"
        manager._base_ports = [8000]
        
        result = manager.start("alice", branch="feature/login")
        
        manager._git.create_worktree.assert_called_once_with("alice", "feature/login")


class TestSandboxManagerStop:
    """Tests for stop method."""

    def test_stop_stops_container(self, tmp_path):
        """Should stop container."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services:\n  dev:\n    ports:\n      - '8000:8000'")
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        
        manager.stop("alice")
        
        manager._docker.compose_stop.assert_called_once_with("alice", "dev")


class TestSandboxManagerStopAll:
    """Tests for stop_all method."""

    def test_stop_all_stops_all_containers(self, tmp_path):
        """Should stop all sandbox containers."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services:\n  dev:\n    ports:\n      - '8000:8000'")
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.list_sandbox_containers.return_value = ["alice-dev-1", "bob-dev-1"]
        
        result = manager.stop_all()
        
        assert len(result) == 2
        assert manager._docker.stop_container.call_count == 2


class TestSandboxManagerRemove:
    """Tests for remove method."""

    def test_remove_stops_and_removes_container_and_worktree(self, tmp_path):
        """Should stop container, remove it, and remove worktree."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services:\n  dev:\n    ports:\n      - '8000:8000'")
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._git = MagicMock()
        
        manager.remove("alice")
        
        manager._docker.compose_stop.assert_called_once()
        manager._docker.compose_rm.assert_called_once()
        manager._git.remove_worktree.assert_called_once_with("alice")


class TestSandboxManagerList:
    """Tests for list method."""

    def test_list_returns_sandbox_info(self, tmp_path):
        """Should return list of SandboxInfo."""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("services:\n  dev:\n    ports:\n      - '8000:8000'")
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.list_sandbox_containers.return_value = ["alice-dev-1"]
        manager._docker.get_container_ports.return_value = {8000: 8001}
        manager._git = MagicMock()
        manager._git.get_current_branch.return_value = "sandbox/alice"
        
        result = manager.list()
        
        assert len(result) == 1
        assert result[0].name == "alice"
        assert result[0].branch == "sandbox/alice"
        assert result[0].ports == {8000: 8001}


class TestSandboxInfo:
    """Tests for SandboxInfo dataclass."""

    def test_sandbox_info_creation(self):
        """Should create SandboxInfo with all fields."""
        info = SandboxInfo(
            name="alice",
            branch="sandbox/alice",
            ports={8000: 8001, 5173: 5174},
            worktree_path=Path("/tmp/.worktrees/alice"),
        )
        
        assert info.name == "alice"
        assert info.branch == "sandbox/alice"
        assert info.ports == {8000: 8001, 5173: 5174}
        assert info.worktree_path == Path("/tmp/.worktrees/alice")
