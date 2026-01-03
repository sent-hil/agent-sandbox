"""E2E test fixtures."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def e2e_project_dir():
    """Create a temporary copy of testproject for e2e tests.
    
    This fixture:
    1. Copies testproject to a temp directory
    2. Initializes a git repo
    3. Yields the path
    4. Cleans up afterward
    """
    # Get the testproject directory (relative to repo root)
    repo_root = Path(__file__).parent.parent.parent
    testproject_src = repo_root / "testproject"
    
    if not testproject_src.exists():
        pytest.skip("testproject directory not found")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / "testproject"
        
        # Copy testproject to temp location, ignoring venv, cache, and .git
        def ignore_patterns(directory, files):
            return {f for f in files if f in {".venv", "__pycache__", ".pytest_cache", "uv.lock", ".git", ".worktrees"}}
        
        shutil.copytree(testproject_src, project_dir, ignore=ignore_patterns)
        
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "add", "."], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )
        
        yield project_dir
        
        # Cleanup: stop any running containers from this test
        try:
            subprocess.run(
                ["docker", "compose", "-p", "test-sandbox", "down", "-v"],
                cwd=project_dir,
                capture_output=True,
            )
        except Exception:
            pass
