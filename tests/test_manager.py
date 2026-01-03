"""Tests for SandboxManager."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_sandbox.manager import SandboxManager, SandboxInfo


class TestSandboxManager:
    """Tests for SandboxManager class."""

    def test_init_with_project_root(self, tmp_path):
        """Should initialize with project root."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"forwardPorts": [8000]}')
        (devcontainer_dir / "Dockerfile").write_text("FROM alpine")
        
        # Initialize git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
        
        manager = SandboxManager(tmp_path)
        assert manager.project_root == tmp_path

    def test_init_auto_detects_project_root(self, tmp_path):
        """Should auto-detect project root from subdirectory."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"forwardPorts": [8000]}')
        (devcontainer_dir / "Dockerfile").write_text("FROM alpine")
        
        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)
        
        # Initialize git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
        
        manager = SandboxManager(subdir)
        assert manager.project_root == tmp_path

    def test_init_raises_when_no_project_root(self, tmp_path):
        """Should raise when no project root found."""
        with pytest.raises(ValueError, match="Could not find devcontainer.json"):
            SandboxManager(tmp_path)


class TestSandboxManagerPortCalculation:
    """Tests for port offset calculation."""

    def test_calculates_next_port_offset_empty(self, tmp_path):
        """Should return 0 when no sandboxes running."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"forwardPorts": [8000]}')
        (devcontainer_dir / "Dockerfile").write_text("FROM alpine")
        
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.list_sandbox_containers.return_value = []
        
        offset = manager._get_next_port_offset()
        assert offset == 0

    def test_calculates_next_port_offset_with_existing(self, tmp_path):
        """Should return next offset based on existing containers."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"forwardPorts": [8000]}')
        (devcontainer_dir / "Dockerfile").write_text("FROM alpine")
        
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.list_sandbox_containers.return_value = ["sandbox-alice", "sandbox-bob"]
        manager._docker.get_sandbox_name_from_container.side_effect = ["alice", "bob"]
        manager._docker.get_container_ports.side_effect = [
            {8000: 8000},  # alice has offset 0
            {8000: 8001},  # bob has offset 1
        ]
        
        offset = manager._get_next_port_offset()
        assert offset == 2


class TestSandboxManagerStart:
    """Tests for start method."""

    def test_start_creates_worktree_and_container(self, tmp_path):
        """Should create worktree and start container."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"forwardPorts": [8000]}')
        (devcontainer_dir / "Dockerfile").write_text("FROM alpine")
        
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.list_sandbox_containers.return_value = []
        manager._docker.container_exists.return_value = False
        manager._git = MagicMock()
        manager._git.create_worktree.return_value = tmp_path / ".worktrees" / "alice"
        manager._git.get_current_branch.return_value = "sandbox/alice"
        
        result = manager.start("alice")
        
        assert result.name == "alice"
        assert result.ports == {8000: 8000}
        manager._git.create_worktree.assert_called_once_with("alice", None)
        manager._docker.start_container.assert_called_once()

    def test_start_skips_if_already_running(self, tmp_path):
        """Should skip start if sandbox already running."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"forwardPorts": [8000]}')
        (devcontainer_dir / "Dockerfile").write_text("FROM alpine")
        
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.container_exists.return_value = True
        manager._docker.get_container_ports.return_value = {8000: 8001}
        manager._git = MagicMock()
        manager._git.get_current_branch.return_value = "sandbox/alice"
        manager._git.worktree_path.return_value = tmp_path / ".worktrees" / "alice"
        
        result = manager.start("alice")
        
        # Should not call start_container since already running
        manager._docker.start_container.assert_not_called()
        assert result.name == "alice"


class TestSandboxManagerStop:
    """Tests for stop method."""

    def test_stop_stops_container(self, tmp_path):
        """Should stop container."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"forwardPorts": [8000]}')
        (devcontainer_dir / "Dockerfile").write_text("FROM alpine")
        
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        
        manager.stop("alice")
        
        manager._docker.stop_container.assert_called_once_with("alice")


class TestSandboxManagerRemove:
    """Tests for remove method."""

    def test_remove_stops_and_removes_container_and_worktree(self, tmp_path):
        """Should stop container, remove it, and remove worktree."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"forwardPorts": [8000]}')
        (devcontainer_dir / "Dockerfile").write_text("FROM alpine")
        
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._git = MagicMock()
        
        manager.remove("alice")
        
        manager._docker.stop_container.assert_called_once_with("alice")
        manager._docker.remove_container.assert_called_once_with("alice")
        manager._git.remove_worktree.assert_called_once_with("alice")


class TestSandboxManagerList:
    """Tests for list method."""

    def test_list_returns_sandbox_info(self, tmp_path):
        """Should return list of SandboxInfo."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer = devcontainer_dir / "devcontainer.json"
        devcontainer.write_text('{"forwardPorts": [8000]}')
        (devcontainer_dir / "Dockerfile").write_text("FROM alpine")
        
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
        
        manager = SandboxManager(tmp_path)
        manager._docker = MagicMock()
        manager._docker.list_sandbox_containers.return_value = ["sandbox-alice"]
        manager._docker.get_container_ports.return_value = {8000: 8001}
        manager._git = MagicMock()
        manager._git.get_current_branch.return_value = "sandbox/alice"
        manager._git.worktree_path.return_value = tmp_path / ".worktrees" / "alice"
        
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
