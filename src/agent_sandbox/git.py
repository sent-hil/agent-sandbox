"""Git operations for agent-sandbox."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

# Fixed path inside containers where the git server (bare repo) is mounted
CONTAINER_GIT_SERVER = "/repo-origin"


class GitClient:
    """Client for Git operations using bare repo architecture."""

    def __init__(self, project_root: Path):
        """Initialize GitClient.

        Args:
            project_root: The project root directory (must be a git repo).
        """
        self.project_root = Path(project_root)

    @property
    def git_server_path(self) -> Path:
        """Get the path to the bare repo (git server)."""
        return self.project_root / ".git-server"

    @property
    def sandboxes_dir(self) -> Path:
        """Get the directory where sandbox clones are stored."""
        return self.project_root / ".sandboxes"

    def sandbox_path(self, name: str) -> Path:
        """Get the path for a specific sandbox clone.

        Args:
            name: The sandbox name.

        Returns:
            Path to the sandbox directory.
        """
        return self.sandboxes_dir / name

    def ensure_git_server(self) -> None:
        """Ensure the bare repo (git server) exists.

        Creates a bare clone of the main repo if it doesn't exist.
        This bare repo acts as the central "origin" for all sandboxes.
        """
        if self.git_server_path.exists():
            return

        # Create bare clone of the main repo
        subprocess.run(
            ["git", "clone", "--bare", ".", str(self.git_server_path)],
            cwd=self.project_root,
            check=True,
            capture_output=True,
        )

    def sync_to_git_server(self) -> None:
        """Push current branch to the git server.

        This ensures the git server has the latest commits from main repo
        before creating a new sandbox.
        """
        if not self.git_server_path.exists():
            return

        # Push all branches to the git server
        subprocess.run(
            ["git", "push", str(self.git_server_path), "--all"],
            cwd=self.project_root,
            capture_output=True,
        )

    def create_sandbox(self, name: str, branch: Optional[str] = None) -> Path:
        """Create a sandbox by cloning from the git server.

        Args:
            name: The sandbox name.
            branch: Optional branch name. If not provided, creates sandbox/<name>.

        Returns:
            Path to the created sandbox.
        """
        sandbox_path = self.sandbox_path(name)

        # Skip if sandbox already exists
        if sandbox_path.exists():
            return sandbox_path

        # Ensure git server exists and is up to date
        self.ensure_git_server()
        self.sync_to_git_server()

        # Create sandboxes directory
        self.sandboxes_dir.mkdir(parents=True, exist_ok=True)

        # Clone from the git server
        subprocess.run(
            ["git", "clone", str(self.git_server_path), str(sandbox_path)],
            cwd=self.project_root,
            check=True,
            capture_output=True,
        )

        # Determine branch name
        if branch is None:
            branch = f"sandbox/{name}"

        # Create and checkout the sandbox branch
        subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=sandbox_path,
            check=True,
            capture_output=True,
        )

        # Configure the clone to use container path for origin
        # This will be the path inside the container
        subprocess.run(
            ["git", "remote", "set-url", "origin", CONTAINER_GIT_SERVER],
            cwd=sandbox_path,
            check=True,
            capture_output=True,
        )

        # Copy AGENTS.md from .devcontainer if it exists
        devcontainer_agents = self.project_root / ".devcontainer" / "AGENTS.md"
        if devcontainer_agents.exists():
            sandbox_agents = sandbox_path / "AGENTS.md"
            # Only copy if sandbox doesn't already have one
            if not sandbox_agents.exists():
                shutil.copy(devcontainer_agents, sandbox_agents)

        return sandbox_path

    def remove_sandbox(self, name: str) -> None:
        """Remove a sandbox clone.

        Args:
            name: The sandbox name.
        """
        sandbox_path = self.sandbox_path(name)

        if sandbox_path.exists():
            shutil.rmtree(sandbox_path, ignore_errors=True)

    def get_current_branch(self, name: str) -> str:
        """Get the current branch for a sandbox.

        Args:
            name: The sandbox name.

        Returns:
            Branch name, or "detached" if not on a branch.
        """
        sandbox_path = self.sandbox_path(name)

        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=sandbox_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 or not result.stdout.strip():
            return "detached"

        return result.stdout.strip()

    def merge_sandbox(self, name: str) -> tuple[bool, str]:
        """Merge a sandbox's changes into the current branch.

        Fetches from the git server and merges the sandbox branch.

        Args:
            name: The sandbox name (or full branch name like 'sandbox/name').

        Returns:
            Tuple of (success, message).
            If success is False, there may be conflicts to resolve.
        """
        # Handle both 'name' and 'sandbox/name' formats
        if name.startswith("sandbox/"):
            branch = name
        else:
            branch = f"sandbox/{name}"

        # Fetch from git server to get the sandbox's pushed commits
        result = subprocess.run(
            ["git", "fetch", str(self.git_server_path), branch],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return False, f"Failed to fetch branch '{branch}': {result.stderr}"

        # Try to merge with auto-resolve
        result = subprocess.run(
            ["git", "merge", "FETCH_HEAD", "-m", f"Merge {branch}"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return True, f"Successfully merged '{branch}'"

        # Check if there are conflicts
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )

        if "UU" in status_result.stdout or "AA" in status_result.stdout:
            return False, (
                f"Merge conflicts detected. Please resolve conflicts in:\n"
                f"{self.project_root}\n"
                f"Then run 'git commit' to complete the merge."
            )

        return False, f"Merge failed: {result.stderr}"

    def branch_exists_in_git_server(self, branch: str) -> bool:
        """Check if a branch exists in the git server.

        Args:
            branch: The branch name to check.

        Returns:
            True if branch exists, False otherwise.
        """
        if not self.git_server_path.exists():
            return False

        result = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=self.git_server_path,
            capture_output=True,
        )
        return result.returncode == 0
