"""Shared test fixtures and configuration."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory with a devcontainer.json file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create .devcontainer directory and devcontainer.json
        devcontainer_dir = project_dir / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_content = """{
    "name": "Test Dev Container",
    "build": {
        "context": "..",
        "dockerfile": "../Dockerfile"
    },
    "forwardPorts": [8000, 5173],
    "workspaceFolder": "/workspaces/project"
}"""
        (devcontainer_dir / "devcontainer.json").write_text(devcontainer_content)

        # Create a minimal Dockerfile
        (project_dir / "Dockerfile").write_text("FROM alpine\nCMD sleep infinity")

        # Initialize a git repo
        subprocess.run(
            ["git", "init"], cwd=project_dir, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=project_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=project_dir,
            capture_output=True,
            check=True,
        )

        # Create a dummy file and commit
        (project_dir / "README.md").write_text("# Test Project")
        subprocess.run(
            ["git", "add", "."], cwd=project_dir, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=project_dir,
            capture_output=True,
            check=True,
        )

        yield project_dir


@pytest.fixture
def mock_docker_client(mocker):
    """Create a mock DockerClient."""
    mock = MagicMock()
    mock.list_sandbox_containers.return_value = []
    mock.get_container_ports.return_value = {}
    mock.container_exists.return_value = False
    return mock


@pytest.fixture
def mock_git_client(mocker):
    """Create a mock GitClient."""
    mock = MagicMock()
    mock.branch_exists.return_value = False
    mock.get_current_branch.return_value = "main"
    mock.get_git_common_dir.return_value = Path("/tmp/test/.git")
    return mock
