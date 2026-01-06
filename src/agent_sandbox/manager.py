"""Sandbox manager - main orchestrator for agent-sandbox."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .docker import DockerClient
from .git import GitClient
from .config import get_default_shell, get_mounts
from .utils import (
    find_devcontainer_json,
    find_project_root,
    get_devcontainer_build_context,
    get_devcontainer_image,
    get_devcontainer_workdir,
    parse_devcontainer_ports,
)

# Type alias for progress callback
ProgressCallback = Callable[[str], None]

# Type alias for output callback (receives line of output)
OutputCallback = Callable[[str], None]


@dataclass
class SandboxInfo:
    """Information about a sandbox."""

    name: str
    branch: str
    ports: dict[int, int]  # container_port -> host_port
    sandbox_path: Path


class SandboxManager:
    """Manager for sandbox lifecycle operations using devcontainers."""

    def __init__(self, path: Optional[Path] = None):
        """Initialize SandboxManager.

        Args:
            path: Path to start searching for project root.
                  If None, uses current directory.

        Raises:
            ValueError: If no project root (devcontainer.json) found.
        """
        if path is None:
            path = Path.cwd()

        # Find project root
        self.project_root = find_project_root(path)
        if self.project_root is None:
            raise ValueError(
                f"Could not find devcontainer.json in {path} or parent directories"
            )

        # Find devcontainer.json
        self.devcontainer_file = find_devcontainer_json(self.project_root)
        if self.devcontainer_file is None:
            raise ValueError(f"Could not find devcontainer.json in {self.project_root}")

        # Parse ports from devcontainer.json
        self._base_ports = parse_devcontainer_ports(self.devcontainer_file)

        # Get build context and dockerfile
        self._context_path, self._dockerfile = get_devcontainer_build_context(
            self.devcontainer_file
        )

        # Get base image (if not building)
        self._base_image = get_devcontainer_image(self.devcontainer_file)

        # Get working directory
        self._workdir = get_devcontainer_workdir(self.devcontainer_file)

        # Initialize clients
        self._docker = DockerClient(self.project_root)
        self._git = GitClient(self.project_root)

    def _get_next_port_offset(self) -> int:
        """Calculate the next available port offset.

        Looks at running sandbox containers and finds the max offset
        used, then returns max + 1.

        Returns:
            The next available port offset.
        """
        if not self._base_ports:
            return 0

        base_port = self._base_ports[0]
        max_offset = -1

        containers = self._docker.list_sandbox_containers()
        for container in containers:
            sandbox_name = self._docker.get_sandbox_name_from_container(container)
            ports = self._docker.get_container_ports(sandbox_name)
            if base_port in ports:
                host_port = ports[base_port]
                offset = host_port - base_port
                if offset > max_offset:
                    max_offset = offset

        return max_offset + 1

    def _build_port_mapping(self, offset: int) -> dict[int, int]:
        """Build port mappings with offset applied.

        Args:
            offset: The port offset to apply.

        Returns:
            Dict mapping container_port -> host_port.
        """
        return {port: port + offset for port in self._base_ports}

    def start(
        self,
        name: str,
        branch: Optional[str] = None,
        on_progress: Optional[ProgressCallback] = None,
        on_build_output: Optional[OutputCallback] = None,
    ) -> SandboxInfo:
        """Start a new sandbox.

        Args:
            name: The sandbox name.
            branch: Optional branch name. Creates sandbox/<name> if not provided.
            on_progress: Optional callback for progress updates.
            on_build_output: Optional callback for build output lines.

        Returns:
            SandboxInfo with details about the started sandbox.
        """

        def progress(msg: str) -> None:
            if on_progress:
                on_progress(msg)

        # Check if already running
        progress("Checking for existing sandbox...")
        if self._docker.container_exists(name):
            # Return existing sandbox info
            ports = self._docker.get_container_ports(name)
            branch_name = self._git.get_current_branch(name)
            sandbox_path = self._git.sandbox_path(name)

            return SandboxInfo(
                name=name,
                branch=branch_name,
                ports=ports,
                sandbox_path=sandbox_path,
            )

        # Create sandbox clone from git server
        progress("Setting up git server...")
        self._git.ensure_git_server()

        progress("Creating sandbox clone...")
        sandbox_path = self._git.create_sandbox(name, branch)

        # Calculate port offset and build port mapping
        offset = self._get_next_port_offset()
        ports = self._build_port_mapping(offset)

        # Start container (this includes building if needed)
        progress("Building container image...")
        self._docker.start_container(
            sandbox_name=name,
            context_path=self._context_path,
            dockerfile=self._dockerfile,
            image=self._base_image,
            workspace_path=sandbox_path,
            workdir=self._workdir,
            ports=ports,
            git_server_path=self._git.git_server_path,
            mounts=get_mounts(self.project_root, self._workdir),
            on_progress=on_progress,
            on_build_output=on_build_output,
        )

        # Get actual branch name
        branch_name = self._git.get_current_branch(name)

        return SandboxInfo(
            name=name,
            branch=branch_name,
            ports=ports,
            sandbox_path=sandbox_path,
        )

    def stop(self, name: str) -> None:
        """Stop a sandbox.

        Args:
            name: The sandbox name.
        """
        self._docker.stop_container(name)

    def stop_all(self, all_namespaces: bool = False) -> list[str]:
        """Stop all running sandboxes.

        Args:
            all_namespaces: If False, only stop sandboxes from this namespace.

        Returns:
            List of stopped sandbox names.
        """
        containers = self._docker.list_sandbox_containers(all_namespaces=all_namespaces)
        stopped = []

        for container in containers:
            name = self._docker.get_sandbox_name_from_container(container)
            self._docker.stop_container(name)
            stopped.append(name)

        return stopped

    def remove(self, name: str) -> None:
        """Remove a sandbox (stop container and delete sandbox clone).

        Args:
            name: The sandbox name.
        """
        # Stop and remove container
        self._docker.stop_container(name)
        self._docker.remove_container(name)

        # Remove sandbox clone
        self._git.remove_sandbox(name)

    def list(self, all_namespaces: bool = False) -> list[SandboxInfo]:
        """List all running sandboxes.

        Args:
            all_namespaces: If False, only return sandboxes from this namespace.

        Returns:
            List of SandboxInfo for each running sandbox.
        """
        containers = self._docker.list_sandbox_containers(all_namespaces=all_namespaces)
        sandboxes = []

        for container in containers:
            # Get sandbox name from container label (more reliable than parsing name)
            name = self._docker.get_sandbox_name_from_container(container)
            sandbox_path = self._git.sandbox_path(name)

            # Handle case where sandbox directory was deleted but container still exists
            if sandbox_path.exists():
                branch = self._git.get_current_branch(name)
            else:
                branch = "(orphaned)"

            # Get ports using the sandbox name
            ports = self._docker.get_container_ports(name)

            sandboxes.append(
                SandboxInfo(
                    name=name,
                    branch=branch,
                    ports=ports,
                    sandbox_path=sandbox_path,
                )
            )

        return sandboxes

    def ports(self, name: str) -> dict[int, int]:
        """Get port mappings for a sandbox.

        Args:
            name: The sandbox name.

        Returns:
            Dict mapping container port to host port.
        """
        return self._docker.get_container_ports(name)

    def logs(self, name: str, follow: bool = True) -> None:
        """Show logs for a sandbox.

        Args:
            name: The sandbox name.
            follow: Whether to follow (stream) logs.
        """
        self._docker.show_logs(name, follow)

    def connect(self, name: str, shell: Optional[str] = None) -> None:
        """Connect to a sandbox's shell.

        Args:
            name: The sandbox name.
            shell: The shell to use. If None, uses user config default or /bin/bash.
        """
        # Use provided shell, or fall back to user config, or /bin/bash
        if shell is None:
            shell = get_default_shell() or "/bin/bash"
        self._docker.exec_shell(name, shell)

    def merge(self, name: str) -> tuple[bool, str]:
        """Merge a sandbox's changes into the current branch.

        Fetches the sandbox branch from the git server and merges it.

        Args:
            name: The sandbox name.

        Returns:
            Tuple of (success, message).
            If success is False, there may be conflicts to resolve.
        """
        return self._git.merge_sandbox(name)
