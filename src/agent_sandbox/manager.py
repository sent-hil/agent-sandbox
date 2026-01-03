"""Sandbox manager - main orchestrator for agent-sandbox."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .docker import DockerClient
from .git import GitClient
from .utils import (
    extract_sandbox_name,
    find_compose_file,
    find_project_root,
    parse_compose_ports,
)


@dataclass
class SandboxInfo:
    """Information about a sandbox."""
    
    name: str
    branch: str
    ports: dict[int, int]  # container_port -> host_port
    worktree_path: Path


class SandboxManager:
    """Manager for sandbox lifecycle operations."""
    
    SERVICE_NAME = "dev"
    
    def __init__(self, path: Optional[Path] = None):
        """Initialize SandboxManager.
        
        Args:
            path: Path to start searching for project root.
                  If None, uses current directory.
                  
        Raises:
            ValueError: If no project root (compose file) found.
        """
        if path is None:
            path = Path.cwd()
        
        # Find project root
        self.project_root = find_project_root(path)
        if self.project_root is None:
            raise ValueError(
                f"Could not find docker-compose.yml in {path} or parent directories"
            )
        
        # Find compose file
        self.compose_file = find_compose_file(self.project_root)
        if self.compose_file is None:
            raise ValueError(f"Could not find compose file in {self.project_root}")
        
        # Parse base ports from compose file
        self._base_ports = parse_compose_ports(self.compose_file, self.SERVICE_NAME)
        
        # Initialize clients
        self._docker = DockerClient(self.compose_file)
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
            ports = self._docker.get_container_ports(container)
            if base_port in ports:
                host_port = ports[base_port]
                offset = host_port - base_port
                if offset > max_offset:
                    max_offset = offset
        
        return max_offset + 1
    
    def _build_port_env(self, offset: int) -> dict[str, str]:
        """Build environment variables for port mappings.
        
        Args:
            offset: The port offset to apply.
            
        Returns:
            Dict of environment variables (SANDBOX_PORT_0, etc.)
        """
        env = {}
        for i, port in enumerate(self._base_ports):
            env[f"SANDBOX_PORT_{i}"] = str(port + offset)
        return env
    
    def start(self, name: str, branch: Optional[str] = None) -> SandboxInfo:
        """Start a new sandbox.
        
        Args:
            name: The sandbox name.
            branch: Optional branch name. Creates sandbox/<name> if not provided.
            
        Returns:
            SandboxInfo with details about the started sandbox.
        """
        container_name = self._docker.container_name(name, self.SERVICE_NAME)
        
        # Check if already running
        if self._docker.container_exists(container_name):
            # Return existing sandbox info
            ports = self._docker.get_container_ports(container_name)
            branch_name = self._git.get_current_branch(name)
            worktree_path = self._git.worktree_path(name)
            
            return SandboxInfo(
                name=name,
                branch=branch_name,
                ports=ports,
                worktree_path=worktree_path,
            )
        
        # Create worktree
        worktree_path = self._git.create_worktree(name, branch)
        
        # Calculate port offset
        offset = self._get_next_port_offset()
        
        # Build environment
        env = self._build_port_env(offset)
        env["WORKSPACE_PATH"] = str(worktree_path)
        env["GIT_DIR"] = str(self._git.get_git_common_dir())
        
        # Start container
        self._docker.compose_up(name, self.SERVICE_NAME, env)
        
        # Build port mapping
        ports = {port: port + offset for port in self._base_ports}
        
        # Get actual branch name
        branch_name = self._git.get_current_branch(name)
        
        return SandboxInfo(
            name=name,
            branch=branch_name,
            ports=ports,
            worktree_path=worktree_path,
        )
    
    def stop(self, name: str) -> None:
        """Stop a sandbox.
        
        Args:
            name: The sandbox name.
        """
        self._docker.compose_stop(name, self.SERVICE_NAME)
    
    def stop_all(self) -> list[str]:
        """Stop all running sandboxes.
        
        Returns:
            List of stopped sandbox names.
        """
        containers = self._docker.list_sandbox_containers()
        stopped = []
        
        for container in containers:
            self._docker.stop_container(container)
            name = extract_sandbox_name(container)
            stopped.append(name)
        
        return stopped
    
    def remove(self, name: str) -> None:
        """Remove a sandbox (stop container and delete worktree).
        
        Args:
            name: The sandbox name.
        """
        # Stop container
        self._docker.compose_stop(name, self.SERVICE_NAME)
        
        # Remove container
        self._docker.compose_rm(name, self.SERVICE_NAME)
        
        # Remove worktree
        self._git.remove_worktree(name)
    
    def list(self) -> list[SandboxInfo]:
        """List all running sandboxes.
        
        Returns:
            List of SandboxInfo for each running sandbox.
        """
        containers = self._docker.list_sandbox_containers()
        sandboxes = []
        
        for container in containers:
            name = extract_sandbox_name(container)
            ports = self._docker.get_container_ports(container)
            branch = self._git.get_current_branch(name)
            worktree_path = self._git.worktree_path(name)
            
            sandboxes.append(SandboxInfo(
                name=name,
                branch=branch,
                ports=ports,
                worktree_path=worktree_path,
            ))
        
        return sandboxes
    
    def ports(self, name: str) -> dict[int, int]:
        """Get port mappings for a sandbox.
        
        Args:
            name: The sandbox name.
            
        Returns:
            Dict mapping container port to host port.
        """
        container_name = self._docker.container_name(name, self.SERVICE_NAME)
        return self._docker.get_container_ports(container_name)
    
    def logs(self, name: str, follow: bool = True) -> None:
        """Show logs for a sandbox.
        
        Args:
            name: The sandbox name.
            follow: Whether to follow (stream) logs.
        """
        self._docker.compose_logs(name, self.SERVICE_NAME, follow)
    
    def connect(self, name: str, shell: str = "sh") -> None:
        """Connect to a sandbox's shell.
        
        Args:
            name: The sandbox name.
            shell: The shell to use (default: sh).
        """
        container_name = self._docker.container_name(name, self.SERVICE_NAME)
        self._docker.exec_shell(container_name, shell)
