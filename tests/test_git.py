"""Tests for Git client."""

from unittest.mock import MagicMock, patch


from agent_sandbox.git import GitClient, CONTAINER_GIT_SERVER


class TestGitClient:
    """Tests for GitClient class."""

    def test_init_with_project_root(self, tmp_path):
        """Should initialize with project root."""
        client = GitClient(tmp_path)
        assert client.project_root == tmp_path

    def test_git_server_path(self, tmp_path):
        """Should return correct git server path."""
        client = GitClient(tmp_path)
        assert client.git_server_path == tmp_path / ".git-server"

    def test_sandboxes_dir(self, tmp_path):
        """Should return correct sandboxes directory."""
        client = GitClient(tmp_path)
        assert client.sandboxes_dir == tmp_path / ".sandboxes"

    def test_sandbox_path(self, tmp_path):
        """Should return correct sandbox path for a name."""
        client = GitClient(tmp_path)
        assert client.sandbox_path("alice") == tmp_path / ".sandboxes" / "alice"


class TestGitClientEnsureGitServer:
    """Tests for ensure_git_server method."""

    def test_creates_git_server_if_not_exists(self, tmp_path):
        """Should create bare repo if it doesn't exist."""
        client = GitClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            client.ensure_git_server()

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "git" in call_args
            assert "clone" in call_args
            assert "--bare" in call_args

    def test_skips_if_git_server_exists(self, tmp_path):
        """Should skip creation if git server already exists."""
        client = GitClient(tmp_path)
        client.git_server_path.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            client.ensure_git_server()

            mock_run.assert_not_called()


class TestGitClientCreateSandbox:
    """Tests for create_sandbox method."""

    def test_creates_sandbox_clone(self, tmp_path):
        """Should create sandbox by cloning from git server."""
        client = GitClient(tmp_path)
        # Create git server directory to skip that step
        client.git_server_path.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = client.create_sandbox("alice")

            assert result == tmp_path / ".sandboxes" / "alice"
            # Should have called git clone, git checkout, and git remote set-url
            assert mock_run.call_count >= 3

    def test_creates_sandbox_with_custom_branch(self, tmp_path):
        """Should create sandbox with custom branch name."""
        client = GitClient(tmp_path)
        client.git_server_path.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = client.create_sandbox("alice", branch="feature/login")

            assert result == tmp_path / ".sandboxes" / "alice"
            # Check that checkout was called with custom branch
            calls = [str(call) for call in mock_run.call_args_list]
            assert any("feature/login" in call for call in calls)

    def test_skips_if_sandbox_exists(self, tmp_path):
        """Should skip creation if sandbox already exists."""
        client = GitClient(tmp_path)
        sandbox_path = tmp_path / ".sandboxes" / "alice"
        sandbox_path.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            result = client.create_sandbox("alice")

            assert result == sandbox_path
            mock_run.assert_not_called()

    def test_copies_agents_md_from_devcontainer(self, tmp_path):
        """Should copy AGENTS.md from .devcontainer to sandbox."""
        client = GitClient(tmp_path)
        client.git_server_path.mkdir(parents=True)

        # Create .devcontainer/AGENTS.md
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        agents_content = "# Sandbox Instructions\nPush with git push origin HEAD"
        (devcontainer_dir / "AGENTS.md").write_text(agents_content)

        sandbox_path = tmp_path / ".sandboxes" / "alice"

        def mock_run_side_effect(cmd, **kwargs):
            # Simulate git clone creating the directory
            if "clone" in cmd:
                sandbox_path.mkdir(parents=True, exist_ok=True)
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_run_side_effect):
            client.create_sandbox("alice")

        # AGENTS.md should be copied
        sandbox_agents = sandbox_path / "AGENTS.md"
        assert sandbox_agents.exists()
        assert sandbox_agents.read_text() == agents_content

    def test_does_not_overwrite_existing_agents_md(self, tmp_path):
        """Should not overwrite AGENTS.md if sandbox already has one."""
        client = GitClient(tmp_path)
        client.git_server_path.mkdir(parents=True)

        # Create .devcontainer/AGENTS.md
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "AGENTS.md").write_text("new content")

        sandbox_path = tmp_path / ".sandboxes" / "alice"

        def mock_run_side_effect(cmd, **kwargs):
            # Simulate git clone creating the directory with existing AGENTS.md
            if "clone" in cmd:
                sandbox_path.mkdir(parents=True, exist_ok=True)
                (sandbox_path / "AGENTS.md").write_text("existing content")
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=mock_run_side_effect):
            client.create_sandbox("alice")

        # Should keep existing content
        assert (sandbox_path / "AGENTS.md").read_text() == "existing content"

    def test_sets_origin_to_container_path(self, tmp_path):
        """Should set origin URL to container git server path."""
        client = GitClient(tmp_path)
        client.git_server_path.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            client.create_sandbox("alice")

            # Find the remote set-url call
            calls = mock_run.call_args_list
            set_url_call = None
            for call in calls:
                args = call[0][0]
                if "set-url" in args:
                    set_url_call = args
                    break

            assert set_url_call is not None
            assert CONTAINER_GIT_SERVER in set_url_call

    def test_sets_git_config_when_provided(self, tmp_path, mocker):
        """Should set git name and email when configured."""
        client = GitClient(tmp_path)
        client.git_server_path.mkdir(parents=True)

        # Mock git config functions
        mocker.patch("agent_sandbox.git.get_git_name", return_value="John Doe")
        mocker.patch("agent_sandbox.git.get_git_email", return_value="john@example.com")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            client.create_sandbox("alice")

            # Check that git config commands were called
            calls = [call[0][0] for call in mock_run.call_args_list]

            # Should have calls for git clone, checkout, set-url, and config
            config_calls = [
                call for call in calls if "config" in call and "user.name" in call
            ]
            assert len(config_calls) == 1
            assert "John Doe" in config_calls[0]

            config_calls = [
                call for call in calls if "config" in call and "user.email" in call
            ]
            assert len(config_calls) == 1
            assert "john@example.com" in config_calls[0]

    def test_skips_git_config_when_not_provided(self, tmp_path, mocker):
        """Should skip git config when not configured."""
        client = GitClient(tmp_path)
        client.git_server_path.mkdir(parents=True)

        # Mock git config functions to return None
        mocker.patch("agent_sandbox.git.get_git_name", return_value=None)
        mocker.patch("agent_sandbox.git.get_git_email", return_value=None)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            client.create_sandbox("alice")

            # Check that no git config commands were called
            calls = [call[0][0] for call in mock_run.call_args_list]
            config_calls = [
                call
                for call in calls
                if "config" in call and ("user.name" in call or "user.email" in call)
            ]
            assert len(config_calls) == 0


class TestGitClientRemoveSandbox:
    """Tests for remove_sandbox method."""

    def test_removes_sandbox(self, tmp_path):
        """Should remove sandbox directory."""
        client = GitClient(tmp_path)
        sandbox_path = tmp_path / ".sandboxes" / "alice"
        sandbox_path.mkdir(parents=True)
        (sandbox_path / "file.txt").write_text("test")

        client.remove_sandbox("alice")

        assert not sandbox_path.exists()

    def test_handles_nonexistent_sandbox(self, tmp_path):
        """Should handle nonexistent sandbox gracefully."""
        client = GitClient(tmp_path)

        # Should not raise
        client.remove_sandbox("nonexistent")


class TestGitClientGetCurrentBranch:
    """Tests for get_current_branch method."""

    def test_gets_current_branch(self, tmp_path):
        """Should get current branch name."""
        client = GitClient(tmp_path)
        # Create sandbox directory
        sandbox_path = tmp_path / ".sandboxes" / "alice"
        sandbox_path.mkdir(parents=True)

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


class TestGitClientMergeSandbox:
    """Tests for merge_sandbox method."""

    def test_merge_success(self, tmp_path):
        """Should return success when merge completes."""
        client = GitClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            # Both fetch and merge succeed
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            success, message = client.merge_sandbox("alice")

            assert success is True
            assert "Successfully merged" in message

    def test_merge_fetch_failure(self, tmp_path):
        """Should return failure when fetch fails."""
        client = GitClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="branch not found"
            )

            success, message = client.merge_sandbox("alice")

            assert success is False
            assert "Failed to fetch" in message

    def test_merge_conflict(self, tmp_path):
        """Should return failure with conflict message."""
        client = GitClient(tmp_path)

        with patch("subprocess.run") as mock_run:

            def side_effect(cmd, **kwargs):
                if "fetch" in cmd:
                    return MagicMock(returncode=0)
                elif "merge" in cmd:
                    return MagicMock(returncode=1, stderr="conflict")
                elif "status" in cmd:
                    return MagicMock(returncode=0, stdout="UU file.txt")
                return MagicMock(returncode=0)

            mock_run.side_effect = side_effect

            success, message = client.merge_sandbox("alice")

            assert success is False
            assert "conflict" in message.lower()

    def test_merge_with_sandbox_prefix(self, tmp_path):
        """Should handle branch name with sandbox/ prefix.

        Regression test: Users may pass 'sandbox/name' instead of just 'name'.
        Previously this would result in 'sandbox/sandbox/name'.
        """
        client = GitClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            success, message = client.merge_sandbox("sandbox/list-rename")

            assert success is True
            # Verify the fetch was called with correct branch (not double-prefixed)
            fetch_call = mock_run.call_args_list[0]
            fetch_cmd = fetch_call[0][0]
            assert "sandbox/list-rename" in fetch_cmd
            assert "sandbox/sandbox/" not in " ".join(fetch_cmd)

    def test_merge_without_sandbox_prefix(self, tmp_path):
        """Should add sandbox/ prefix when not provided."""
        client = GitClient(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            success, message = client.merge_sandbox("alice")

            assert success is True
            # Verify the fetch was called with sandbox/alice
            fetch_call = mock_run.call_args_list[0]
            fetch_cmd = fetch_call[0][0]
            assert "sandbox/alice" in fetch_cmd
