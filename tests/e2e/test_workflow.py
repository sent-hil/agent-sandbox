"""End-to-end tests for full sandbox workflow."""

import subprocess
import time
from pathlib import Path

import pytest

from agent_sandbox.manager import SandboxManager


pytestmark = pytest.mark.e2e


class TestFullWorkflow:
    """E2E tests for the full sandbox workflow."""

    def test_start_list_stop_remove(self, e2e_project_dir):
        """Test complete lifecycle: start -> list -> stop -> remove."""
        manager = SandboxManager(e2e_project_dir)
        sandbox_name = "e2e-test"
        
        try:
            # Start sandbox
            info = manager.start(sandbox_name)
            
            assert info.name == sandbox_name
            assert info.branch == f"sandbox/{sandbox_name}"
            assert 8000 in info.ports
            assert info.worktree_path.exists()
            
            # Wait for container to be ready (needs time for uv sync + uvicorn startup)
            time.sleep(10)
            
            # List sandboxes
            sandboxes = manager.list()
            assert len(sandboxes) >= 1
            names = [s.name for s in sandboxes]
            assert sandbox_name in names
            
            # Check ports
            ports = manager.ports(sandbox_name)
            assert 8000 in ports
            
            # Verify the app is responding
            host_port = ports[8000]
            result = subprocess.run(
                ["curl", "-s", f"http://localhost:{host_port}/health"],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            assert "ok" in result.stdout
            
            # Stop sandbox
            manager.stop(sandbox_name)
            
            # Verify stopped (container should not be running)
            time.sleep(1)
            sandboxes_after_stop = manager.list()
            names_after_stop = [s.name for s in sandboxes_after_stop]
            assert sandbox_name not in names_after_stop
            
        finally:
            # Always cleanup
            try:
                manager.remove(sandbox_name)
            except Exception:
                pass

    def test_start_with_existing_branch(self, e2e_project_dir):
        """Test starting sandbox with an existing branch."""
        manager = SandboxManager(e2e_project_dir)
        sandbox_name = "e2e-branch-test"
        branch_name = "test-feature"
        
        try:
            # Create a branch first
            subprocess.run(
                ["git", "branch", branch_name],
                cwd=e2e_project_dir,
                check=True,
                capture_output=True,
            )
            
            # Start sandbox with that branch
            info = manager.start(sandbox_name, branch=branch_name)
            
            assert info.name == sandbox_name
            assert info.branch == branch_name
            
        finally:
            # Cleanup
            try:
                manager.remove(sandbox_name)
                subprocess.run(
                    ["git", "branch", "-D", branch_name],
                    cwd=e2e_project_dir,
                    capture_output=True,
                )
            except Exception:
                pass

    def test_multiple_sandboxes_different_ports(self, e2e_project_dir):
        """Test that multiple sandboxes get different ports."""
        manager = SandboxManager(e2e_project_dir)
        sandbox1 = "e2e-multi-1"
        sandbox2 = "e2e-multi-2"
        
        try:
            # Start first sandbox
            info1 = manager.start(sandbox1)
            port1 = info1.ports[8000]
            
            # Wait for first to be ready before starting second
            time.sleep(5)
            
            # Start second sandbox
            info2 = manager.start(sandbox2)
            port2 = info2.ports[8000]
            
            # Ports should be different
            assert port1 != port2
            
            # Both should be accessible (needs time for uv sync + uvicorn startup)
            time.sleep(10)
            
            # Get actual ports from running containers
            actual_port1 = manager.ports(sandbox1).get(8000, port1)
            actual_port2 = manager.ports(sandbox2).get(8000, port2)
            
            for port in [actual_port1, actual_port2]:
                result = subprocess.run(
                    ["curl", "-s", f"http://localhost:{port}/health"],
                    capture_output=True,
                    text=True,
                )
                assert result.returncode == 0
                assert "ok" in result.stdout
                
        finally:
            # Cleanup
            for name in [sandbox1, sandbox2]:
                try:
                    manager.remove(name)
                except Exception:
                    pass


class TestCLI:
    """E2E tests for CLI commands."""

    def test_cli_help(self):
        """Test CLI help command works."""
        result = subprocess.run(
            ["uv", "run", "agent-sandbox", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "start" in result.stdout
        assert "stop" in result.stdout
        assert "list" in result.stdout
        assert "connect" in result.stdout
        assert "rm" in result.stdout

    def test_cli_version(self):
        """Test CLI version command works."""
        result = subprocess.run(
            ["uv", "run", "agent-sandbox", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "0.1.0" in result.stdout
