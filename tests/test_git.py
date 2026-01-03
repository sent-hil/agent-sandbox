"""Tests for Git client."""

from unittest.mock import MagicMock, patch


from agent_sandbox.git import GitClient


class TestGitClient:
    """Tests for GitClient class."""

    def test_init_with_project_root(self, tmp_path):
        """Should initialize with project root."""
        client = GitClient(tmp_path)
        assert client.project_root == tmp_path

    def test_worktree_dir(self, tmp_path):
        """Should return correct worktree directory."""
        client = GitClient(tmp_path)
        assert client.worktree_dir == tmp_path / ".worktrees"

    def test_worktree_path(self, tmp_path):
        """Should return correct worktree path for a sandbox."""
        client = GitClient(tmp_path)
        assert client.worktree_path("alice") == tmp_path / ".worktrees" / "alice"


class TestGitClientBranchExists:
    """Tests for branch_exists method."""

    def test_branch_exists_true(self, tmp_path):
        """Should return True when branch exists."""
        client = GitClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = client.branch_exists("main")

            assert result is True
            mock_run.assert_called_once()

    def test_branch_exists_false(self, tmp_path):
        """Should return False when branch doesn't exist."""
        client = GitClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            result = client.branch_exists("nonexistent")

            assert result is False


class TestGitClientCreateWorktree:
    """Tests for create_worktree method."""

    def test_creates_worktree_new_branch(self, tmp_path):
        """Should create worktree with new branch."""
        client = GitClient(tmp_path)

        with patch.object(client, "branch_exists", return_value=False):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                result = client.create_worktree("alice")

                assert result == tmp_path / ".worktrees" / "alice"
                # Should create directory and call git worktree add with -b flag
                calls = mock_run.call_args_list
                assert any("-b" in str(call) for call in calls)

    def test_creates_worktree_existing_branch(self, tmp_path):
        """Should create worktree for existing branch."""
        client = GitClient(tmp_path)

        with patch.object(client, "branch_exists", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                result = client.create_worktree("alice", branch="feature/login")

                assert result == tmp_path / ".worktrees" / "alice"

    def test_skips_if_worktree_exists(self, tmp_path):
        """Should skip creation if worktree already exists."""
        client = GitClient(tmp_path)
        worktree_path = tmp_path / ".worktrees" / "alice"
        worktree_path.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            result = client.create_worktree("alice")

            assert result == worktree_path
            # Should not call git commands
            mock_run.assert_not_called()


class TestGitClientRemoveWorktree:
    """Tests for remove_worktree method."""

    def test_removes_worktree(self, tmp_path):
        """Should remove worktree."""
        client = GitClient(tmp_path)
        worktree_path = tmp_path / ".worktrees" / "alice"
        worktree_path.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            client.remove_worktree("alice")

            mock_run.assert_called()

    def test_handles_nonexistent_worktree(self, tmp_path):
        """Should handle nonexistent worktree gracefully."""
        client = GitClient(tmp_path)

        # Should not raise
        client.remove_worktree("nonexistent")


class TestGitClientGetCurrentBranch:
    """Tests for get_current_branch method."""

    def test_gets_current_branch(self, tmp_path):
        """Should get current branch name."""
        client = GitClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="sandbox/alice\n")

            result = client.get_current_branch("alice")

            assert result == "sandbox/alice"

    def test_returns_detached_on_failure(self, tmp_path):
        """Should return 'detached' on failure."""
        client = GitClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")

            result = client.get_current_branch("alice")

            assert result == "detached"
