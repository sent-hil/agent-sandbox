"""Docker operations for agent-sandbox."""

import os
import re
import subprocess
from pathlib import Path


# Label used to identify sandbox containers
SANDBOX_LABEL = "agent-sandbox.managed=true"


class DockerClient:
    """Client for Docker operations with devcontainers."""
    
    def __init__(self, project_root: Path):
        """Initialize DockerClient.
        
        Args:
            project_root: Path to the project root.
        """
        self.project_root = Path(project_root)
    
    def container_name(self, sandbox_name: str) -> str:
        """Get the container name for a sandbox.
        
        Args:
            sandbox_name: The sandbox name.
            
        Returns:
            The container name.
        """
        return f"sandbox-{sandbox_name}"
    
    def image_name(self, sandbox_name: str) -> str:
        """Get the image name for a sandbox.
        
        Args:
            sandbox_name: The sandbox name.
            
        Returns:
            The image name.
        """
        return f"sandbox-{sandbox_name}:latest"
    
    def build_image(
        self,
        sandbox_name: str,
        context_path: Path,
        dockerfile: str,
    ) -> None:
        """Build a Docker image from a Dockerfile.
        
        Args:
            sandbox_name: The sandbox name (used for image tag).
            context_path: The build context directory.
            dockerfile: Path to Dockerfile relative to context.
            
        Raises:
            RuntimeError: If build fails.
        """
        image_name = self.image_name(sandbox_name)
        
        cmd = [
            "docker", "build",
            "-t", image_name,
            "-f", str(context_path / dockerfile),
            str(context_path),
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"docker build failed: {result.stderr}")
    
    def run_container(
        self,
        sandbox_name: str,
        image: str,
        workspace_path: Path,
        workdir: str,
        ports: dict[int, int],
    ) -> None:
        """Run a container from an image.
        
        Args:
            sandbox_name: The sandbox name.
            image: The image to run.
            workspace_path: Host path to mount as workspace.
            workdir: Working directory inside container.
            ports: Dict mapping container_port -> host_port.
            
        Raises:
            RuntimeError: If run fails.
        """
        container_name = self.container_name(sandbox_name)
        
        cmd = [
            "docker", "run",
            "-d",  # Detached
            "--name", container_name,
            "--label", SANDBOX_LABEL,
            "--label", f"agent-sandbox.name={sandbox_name}",
            "-v", f"{workspace_path}:{workdir}",
            "-w", workdir,
        ]
        
        # Add port mappings
        for container_port, host_port in ports.items():
            cmd.extend(["-p", f"{host_port}:{container_port}"])
        
        # Add the image
        cmd.append(image)
        
        # Keep container running with sleep infinity
        cmd.extend(["sleep", "infinity"])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"docker run failed: {result.stderr}")
    
    def start_container(
        self,
        sandbox_name: str,
        context_path: Path,
        dockerfile: str,
        image: str | None,
        workspace_path: Path,
        workdir: str,
        ports: dict[int, int],
    ) -> None:
        """Build (if needed) and start a container for a sandbox.
        
        Args:
            sandbox_name: The sandbox name.
            context_path: Build context path (if building).
            dockerfile: Dockerfile path relative to context (if building).
            image: Base image name (if not building).
            workspace_path: Host path to mount as workspace.
            workdir: Working directory inside container.
            ports: Dict mapping container_port -> host_port.
            
        Raises:
            RuntimeError: If build or run fails.
        """
        # Determine which image to use
        if dockerfile:
            # Build from Dockerfile
            self.build_image(sandbox_name, context_path, dockerfile)
            run_image = self.image_name(sandbox_name)
        elif image:
            # Use specified image
            run_image = image
        else:
            raise RuntimeError("No Dockerfile or image specified in devcontainer.json")
        
        # Run the container
        self.run_container(
            sandbox_name=sandbox_name,
            image=run_image,
            workspace_path=workspace_path,
            workdir=workdir,
            ports=ports,
        )
    
    def stop_container(self, sandbox_name: str) -> None:
        """Stop a sandbox container.
        
        Args:
            sandbox_name: The sandbox name.
        """
        container_name = self.container_name(sandbox_name)
        cmd = ["docker", "stop", container_name]
        subprocess.run(cmd, capture_output=True)
    
    def remove_container(self, sandbox_name: str) -> None:
        """Remove a sandbox container.
        
        Args:
            sandbox_name: The sandbox name.
        """
        container_name = self.container_name(sandbox_name)
        cmd = ["docker", "rm", "-f", container_name]
        subprocess.run(cmd, capture_output=True)
    
    def container_exists(self, sandbox_name: str) -> bool:
        """Check if a sandbox container exists and is running.
        
        Args:
            sandbox_name: The sandbox name.
            
        Returns:
            True if container is running, False otherwise.
        """
        container_name = self.container_name(sandbox_name)
        
        cmd = [
            "docker", "ps",
            "--filter", f"name=^{container_name}$",
            "--format", "{{.Names}}",
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return container_name in result.stdout
    
    def list_sandbox_containers(self) -> list[str]:
        """List all running sandbox containers.
        
        Returns:
            List of container names.
        """
        cmd = [
            "docker", "ps",
            "--filter", f"label={SANDBOX_LABEL}",
            "--format", "{{.Names}}",
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return []
        
        containers = result.stdout.strip().split("\n")
        return [c for c in containers if c]
    
    def get_container_ports(self, sandbox_name: str) -> dict[int, int]:
        """Get port mappings for a sandbox container.
        
        Args:
            sandbox_name: The sandbox name.
            
        Returns:
            Dict mapping container port to host port.
        """
        container_name = self.container_name(sandbox_name)
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
    
    def get_sandbox_name_from_container(self, container_name: str) -> str:
        """Extract sandbox name from container name.
        
        Args:
            container_name: The container name (sandbox-<name>).
            
        Returns:
            The sandbox name.
        """
        if container_name.startswith("sandbox-"):
            return container_name[8:]
        return container_name
    
    def show_logs(self, sandbox_name: str, follow: bool = True) -> None:
        """Show logs for a sandbox container.
        
        Args:
            sandbox_name: The sandbox name.
            follow: Whether to follow logs.
        """
        container_name = self.container_name(sandbox_name)
        
        cmd = ["docker", "logs"]
        if follow:
            cmd.append("-f")
        cmd.append(container_name)
        
        # Run interactively
        subprocess.run(cmd)
    
    def exec_shell(self, sandbox_name: str, shell: str = "sh") -> None:
        """Execute an interactive shell in a sandbox container.
        
        Args:
            sandbox_name: The sandbox name.
            shell: The shell to use (default: sh).
        """
        container_name = self.container_name(sandbox_name)
        cmd = ["docker", "exec", "-it", container_name, shell]
        
        # Run interactively (replace current process)
        os.execvp("docker", cmd)
