"""Tests for init module."""

import subprocess


from agent_sandbox.init import find_git_root, create_devcontainer


class TestFindGitRoot:
    """Tests for find_git_root function."""

    def test_finds_git_root(self, tmp_path):
        """Should find git root directory."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        # Create subdirectory
        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)

        result = find_git_root(subdir)
        assert result == tmp_path

    def test_returns_none_for_non_git(self, tmp_path):
        """Should return None when not in a git repo."""
        result = find_git_root(tmp_path)
        assert result is None


class TestCreateDevcontainer:
    """Tests for create_devcontainer function."""

    def test_creates_devcontainer_files(self, tmp_path):
        """Should create .devcontainer directory with Dockerfile and devcontainer.json."""
        create_devcontainer(tmp_path)

        devcontainer_dir = tmp_path / ".devcontainer"
        assert devcontainer_dir.exists()

        dockerfile = devcontainer_dir / "Dockerfile"
        assert dockerfile.exists()
        assert "ubuntu" in dockerfile.read_text().lower()

        devcontainer_json = devcontainer_dir / "devcontainer.json"
        assert devcontainer_json.exists()
        assert "Agent Sandbox" in devcontainer_json.read_text()

    def test_uses_custom_project_name(self, tmp_path):
        """Should use custom project name in devcontainer.json."""
        create_devcontainer(tmp_path, project_name="my-project")

        devcontainer_json = tmp_path / ".devcontainer" / "devcontainer.json"
        content = devcontainer_json.read_text()
        assert "my-project" in content

    def test_uses_directory_name_by_default(self, tmp_path):
        """Should use directory name as project name by default."""
        create_devcontainer(tmp_path)

        devcontainer_json = tmp_path / ".devcontainer" / "devcontainer.json"
        content = devcontainer_json.read_text()
        assert tmp_path.name in content

    def test_dockerfile_includes_claude_code(self, tmp_path):
        """Should include Claude Code installation in Dockerfile."""
        create_devcontainer(tmp_path)

        dockerfile = tmp_path / ".devcontainer" / "Dockerfile"
        content = dockerfile.read_text()
        assert "claude-code" in content.lower()

    def test_dockerfile_includes_uv(self, tmp_path):
        """Should include uv installation in Dockerfile."""
        create_devcontainer(tmp_path)

        dockerfile = tmp_path / ".devcontainer" / "Dockerfile"
        content = dockerfile.read_text()
        assert "uv" in content

    def test_overwrites_existing(self, tmp_path):
        """Should overwrite existing devcontainer files."""
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "Dockerfile").write_text("old content")

        create_devcontainer(tmp_path)

        dockerfile = devcontainer_dir / "Dockerfile"
        assert "old content" not in dockerfile.read_text()
