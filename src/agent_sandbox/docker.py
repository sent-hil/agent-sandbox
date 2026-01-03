"""Docker operations for agent-sandbox."""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


class DockerClient:
    """Client for Docker and Docker Compose operations."""
    
    def __init__(self, compose_file: Path):
        """Initialize DockerClient.
        
        Args:
            compose_file: Path to the docker-compose file.
        """
        self.compose_file = Path(compose_file)
    
    def container_name(self, project_name: str, service: str) -> str:
        """Get the container name for a project and service.
        
        Tries both Docker Compose (hyphen) and podman-compose (underscore) conventions.
        
        Args:
            project_name: The Docker Compose project name.
            service: The service name.
            
        Returns:
            The actual container name if found, or the hyphen format as default.
        """
        # Docker Compose uses hyphens, podman-compose uses underscores
        hyphen_name = f"{project_name}-{service}-1"
        underscore_name = f"{project_name}_{service}_1"
        
        # Check which one exists
        for name in [hyphen_name, underscore_name]:
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
            )
            if name in result.stdout:
                return name
        
        # Default to hyphen format
        return hyphen_name
    
    def compose_up(
        self,
        project_name: str,
        service: str,
        env: dict[str, str],
    ) -> None:
        """Start a service with docker compose up.
        
        Args:
            project_name: The Docker Compose project name.
            service: The service to start.
            env: Environment variables to pass to compose.
            
        Raises:
            RuntimeError: If compose up fails.
        """
        cmd = [
            "docker", "compose",
            "-f", str(self.compose_file),
            "-p", project_name,
            "up", "-d", service,
        ]
        
        # Merge with current environment
        full_env = os.environ.copy()
        full_env.update(env)
        
        result = subprocess.run(
            cmd,
            env=full_env,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"docker compose up failed: {result.stderr}")
    
    def compose_stop(self, project_name: str, service: str) -> None:
        """Stop a service with docker compose stop.
        
        Args:
            project_name: The Docker Compose project name.
            service: The service to stop.
        """
        cmd = [
            "docker", "compose",
            "-f", str(self.compose_file),
            "-p", project_name,
            "stop", service,
        ]
        
        subprocess.run(cmd, capture_output=True)
    
    def compose_rm(self, project_name: str, service: str) -> None:
        """Remove a service container with docker compose rm.
        
        Args:
            project_name: The Docker Compose project name.
            service: The service to remove.
        """
        cmd = [
            "docker", "compose",
            "-f", str(self.compose_file),
            "-p", project_name,
            "rm", "-f", service,
        ]
        
        subprocess.run(cmd, capture_output=True)
    
    def compose_logs(
        self,
        project_name: str,
        service: str,
        follow: bool = True,
    ) -> None:
        """Show logs for a service.
        
        Args:
            project_name: The Docker Compose project name.
            service: The service to show logs for.
            follow: Whether to follow logs (stream).
        """
        cmd = [
            "docker", "compose",
            "-f", str(self.compose_file),
            "-p", project_name,
            "logs",
        ]
        
        if follow:
            cmd.append("-f")
        
        cmd.append(service)
        
        # Run interactively (don't capture output)
        subprocess.run(cmd)
    
    def list_sandbox_containers(self) -> list[str]:
        """List all running sandbox containers.
        
        Returns:
            List of container names.
        """
        cmd = [
            "docker", "ps",
            "--filter", "label=com.docker.compose.service=dev",
            "--format", "{{.Names}}",
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return []
        
        containers = result.stdout.strip().split("\n")
        return [c for c in containers if c]
    
    def get_container_ports(self, container_name: str) -> dict[int, int]:
        """Get port mappings for a container.
        
        Args:
            container_name: The container name.
            
        Returns:
            Dict mapping container port to host port.
        """
        cmd = ["docker", "port", container_name]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {}
        
        ports = {}
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            
            # Format: "8000/tcp -> 0.0.0.0:8001"
            match = re.match(r"(\d+)/\w+ -> [\d.]+:(\d+)", line)
            if match:
                container_port = int(match.group(1))
                host_port = int(match.group(2))
                ports[container_port] = host_port
        
        return ports
    
    def container_exists(self, container_name: str) -> bool:
        """Check if a container exists and is running.
        
        Args:
            container_name: The container name (can be hyphen or underscore format).
            
        Returns:
            True if container is running, False otherwise.
        """
        # Try both hyphen and underscore formats
        base_name = container_name.replace("-", "_").replace("__", "_")
        alt_name = container_name.replace("_", "-").replace("--", "-")
        
        for name in [container_name, base_name, alt_name]:
            cmd = [
                "docker", "ps",
                "--filter", f"name=^{name}$",
                "--format", "{{.Names}}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if name in result.stdout:
                return True
        
        return False
    
    def stop_container(self, container_name: str) -> None:
        """Stop a container by name.
        
        Args:
            container_name: The container name to stop.
        """
        cmd = ["docker", "stop", container_name]
        subprocess.run(cmd, capture_output=True)
    
    def exec_shell(
        self,
        container_name: str,
        shell: str = "sh",
    ) -> None:
        """Execute an interactive shell in a container.
        
        Args:
            container_name: The container name.
            shell: The shell to use (default: sh).
        """
        cmd = ["docker", "exec", "-it", container_name, shell]
        
        # Run interactively (replace current process)
        os.execvp("docker", cmd)
