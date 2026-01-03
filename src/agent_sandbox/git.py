"""Git operations for agent-sandbox."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional


class GitClient:
    """Client for Git worktree operations."""

    def __init__(self, project_root: Path):
        """Initialize GitClient.

        Args:
            project_root: The project root directory (must be a git repo).
        """
        self.project_root = Path(project_root)

    @property
    def worktree_dir(self) -> Path:
        """Get the directory where worktrees are stored."""
        return self.project_root / ".worktrees"

    def worktree_path(self, name: str) -> Path:
        """Get the path for a specific worktree.

        Args:
            name: The sandbox name.

        Returns:
            Path to the worktree directory.
        """
        return self.worktree_dir / name

    def branch_exists(self, branch: str) -> bool:
        """Check if a branch exists.

        Args:
            branch: The branch name to check.

        Returns:
            True if branch exists, False otherwise.
        """
        result = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=self.project_root,
            capture_output=True,
        )
        return result.returncode == 0

    def create_worktree(self, name: str, branch: Optional[str] = None) -> Path:
        """Create a git worktree for a sandbox.

        Args:
            name: The sandbox name.
            branch: Optional branch name. If not provided, creates sandbox/<name>.
                   If provided and exists, checks out that branch.
                   If provided and doesn't exist, creates new branch from HEAD.

        Returns:
            Path to the created worktree.
        """
        worktree_path = self.worktree_path(name)

        # Skip if worktree already exists
        if worktree_path.exists():
            return worktree_path

        # Create worktrees directory
        self.worktree_dir.mkdir(parents=True, exist_ok=True)

        # Determine branch name
        if branch is None:
            branch = f"sandbox/{name}"

        # Create worktree
        if self.branch_exists(branch):
            # Use existing branch
            subprocess.run(
                ["git", "worktree", "add", str(worktree_path), branch],
                cwd=self.project_root,
                check=True,
                capture_output=True,
            )
        else:
            # Create new branch
            subprocess.run(
                ["git", "worktree", "add", "-b", branch, str(worktree_path)],
                cwd=self.project_root,
                check=True,
                capture_output=True,
            )

        return worktree_path

    def remove_worktree(self, name: str) -> None:
        """Remove a git worktree.

        Args:
            name: The sandbox name.
        """
        worktree_path = self.worktree_path(name)

        if not worktree_path.exists():
            return

        # Try git worktree remove first
        result = subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=self.project_root,
            capture_output=True,
        )

        # Fall back to manual removal if git command fails
        if result.returncode != 0 and worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)

    def get_current_branch(self, name: str) -> str:
        """Get the current branch for a worktree.

        Args:
            name: The sandbox name.

        Returns:
            Branch name, or "detached" if not on a branch.
        """
        worktree_path = self.worktree_path(name)

        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 or not result.stdout.strip():
            return "detached"

        return result.stdout.strip()

    def get_git_common_dir(self) -> Path:
        """Get the main .git directory (handles worktrees).

        Returns:
            Path to the main .git directory.
        """
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=True,
        )

        git_dir = result.stdout.strip()

        # Make absolute if relative
        if not git_dir.startswith("/"):
            git_dir = str(self.project_root / git_dir)

        return Path(git_dir).resolve()
