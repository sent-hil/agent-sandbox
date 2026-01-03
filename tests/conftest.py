"""Shared test fixtures and configuration."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory with a docker-compose.yml file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # Create a minimal docker-compose.yml
        compose_content = """services:
  dev:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "${SANDBOX_PORT_0:-8000}:8000"
      - "${SANDBOX_PORT_1:-5173}:5173"
    volumes:
      - ${WORKSPACE_PATH:-.}:/app
"""
        (project_dir / "docker-compose.yml").write_text(compose_content)
        
        # Initialize a git repo
        os.system(f"git init -q {project_dir}")
        os.system(f"git -C {project_dir} config user.email 'test@test.com'")
        os.system(f"git -C {project_dir} config user.name 'Test'")
        
        # Create a dummy file and commit
        (project_dir / "README.md").write_text("# Test Project")
        os.system(f"git -C {project_dir} add .")
        os.system(f"git -C {project_dir} commit -q -m 'Initial commit'")
        
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
