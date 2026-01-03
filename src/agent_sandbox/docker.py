"""Docker operations for agent-sandbox."""

import os
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

# Type alias for progress callback
ProgressCallback = Callable[[str], None]

# Type alias for output callback (receives line of output)
OutputCallback = Callable[[str], None]

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
        from .utils import get_project_namespace

        self.namespace = get_project_namespace(project_root)

    def container_name(self, sandbox_name: str) -> str:
        """Get the container name for a sandbox.

        Args:
            sandbox_name: The sandbox name.

        Returns:
            The container name.
        """
        return f"sandbox-{self.namespace}-{sandbox_name}"

    def image_name(self, sandbox_name: str) -> str:
        """Get the image name for a sandbox.

        Args:
            sandbox_name: The sandbox name.

        Returns:
            The image name.
        """
        return f"sandbox-{self.namespace}-{sandbox_name}:latest"

    def build_image(
        self,
        sandbox_name: str,
        context_path: Path,
        dockerfile: str,
        on_output: Optional[OutputCallback] = None,
    ) -> None:
        """Build a Docker image from a Dockerfile.

        Args:
            sandbox_name: The sandbox name (used for image tag).
            context_path: The build context directory.
            dockerfile: Path to Dockerfile relative to context.
            on_output: Optional callback for build output lines.

        Raises:
            RuntimeError: If build fails.
        """
        image_name = self.image_name(sandbox_name)

        cmd = [
            "docker",
            "build",
            "-t",
            image_name,
            "-f",
            str(context_path / dockerfile),
            str(context_path),
        ]

        # Stream output if callback provided
        if on_output:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            output_lines: list[str] = []
            if process.stdout:
                for line in process.stdout:
                    line = line.rstrip()
                    output_lines.append(line)
                    on_output(line)
            process.wait()
            if process.returncode != 0:
                raise RuntimeError("docker build failed:\n" + "\n".join(output_lines[-20:]))
        else:
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
        git_server_path: Optional[Path] = None,
    ) -> None:
        """Run a container from an image.

        Args:
            sandbox_name: The sandbox name.
            image: The image to run.
            workspace_path: Host path to mount as workspace.
            workdir: Working directory inside container.
            ports: Dict mapping container_port -> host_port.
            git_server_path: Host path to bare repo (mounted at /repo-origin).

        Raises:
            RuntimeError: If run fails.
        """
        container_name = self.container_name(sandbox_name)

        cmd = [
            "docker",
            "run",
            "-d",  # Detached
            "-u",
            "root",  # Run as root for bind mount permissions
            "--name",
            container_name,
            "--label",
            SANDBOX_LABEL,
            "--label",
            f"agent-sandbox.name={sandbox_name}",
            "--label",
            f"agent-sandbox.namespace={self.namespace}",
            "-v",
            f"{workspace_path}:{workdir}",
            "-w",
            workdir,
        ]

        # Mount git server if provided
        if git_server_path:
            cmd.extend(["-v", f"{git_server_path}:/repo-origin"])

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
        git_server_path: Optional[Path] = None,
        on_progress: Optional[ProgressCallback] = None,
        on_build_output: Optional[OutputCallback] = None,
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
            git_server_path: Host path to bare repo (mounted at /repo-origin).
            on_progress: Optional callback for progress updates.
            on_build_output: Optional callback for build output lines.

        Raises:
            RuntimeError: If build or run fails.
        """

        def progress(msg: str) -> None:
            if on_progress:
                on_progress(msg)

        # Determine which image to use
        if dockerfile:
            # Build from Dockerfile
            progress("Building container image...")
            self.build_image(sandbox_name, context_path, dockerfile, on_output=on_build_output)
            run_image = self.image_name(sandbox_name)
        elif image:
            # Use specified image
            progress(f"Using image {image}...")
            run_image = image
        else:
            raise RuntimeError("No Dockerfile or image specified in devcontainer.json")

        # Run the container
        progress("Starting container...")
        self.run_container(
            sandbox_name=sandbox_name,
            image=run_image,
            workspace_path=workspace_path,
            workdir=workdir,
            ports=ports,
            git_server_path=git_server_path,
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
            "docker",
            "ps",
            "--filter",
            f"name=^{container_name}$",
            "--format",
            "{{.Names}}",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return container_name in result.stdout

    def list_sandbox_containers(self, all_namespaces: bool = False) -> list[str]:
        """List all running sandbox containers.

        Args:
            all_namespaces: If False, only return containers from this namespace.

        Returns:
            List of container names.
        """
        if all_namespaces:
            # Get all sandbox containers
            cmd = [
                "docker",
                "ps",
                "--filter",
                f"label={SANDBOX_LABEL}",
                "--format",
                "{{.Names}}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return []
            containers = result.stdout.strip().split("\n")
            return [c for c in containers if c]

        # For namespace filtering, we need to handle both:
        # 1. Containers with matching namespace label (new style)
        # 2. Legacy containers without namespace label but with sandbox dir in this project

        # First get containers with matching namespace label
        cmd = [
            "docker",
            "ps",
            "--filter",
            f"label={SANDBOX_LABEL}",
            "--filter",
            f"label=agent-sandbox.namespace={self.namespace}",
            "--format",
            "{{.Names}}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        namespaced_containers = []
        if result.returncode == 0 and result.stdout.strip():
            namespaced_containers = [c for c in result.stdout.strip().split("\n") if c]

        # Then get legacy containers (no namespace label) and check if they belong here
        cmd = [
            "docker",
            "ps",
            "--filter",
            f"label={SANDBOX_LABEL}",
            "--format",
            "{{.Label \"agent-sandbox.name\"}}:{{.Names}}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            sandboxes_dir = self.project_root / ".sandboxes"
            for line in result.stdout.strip().split("\n"):
                if not line or ":" not in line:
                    continue
                sandbox_name, container_name = line.split(":", 1)
                # Skip if already in namespaced list
                if container_name in namespaced_containers:
                    continue
                # Check if this sandbox belongs to this project (has a directory here)
                if sandbox_name and (sandboxes_dir / sandbox_name).exists():
                    namespaced_containers.append(container_name)

        return namespaced_containers

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

        Uses the agent-sandbox.name label if available, otherwise falls back
        to parsing the container name.

        Args:
            container_name: The container name.

        Returns:
            The sandbox name.
        """
        # Try to get the name from the label first (most reliable)
        cmd = [
            "docker",
            "inspect",
            "--format",
            "{{index .Config.Labels \"agent-sandbox.name\"}}",
            container_name,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        # Fall back to parsing container name
        from .utils import extract_sandbox_name

        return extract_sandbox_name(container_name)

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

    def shell_exists(self, sandbox_name: str, shell: str) -> bool:
        """Check if a shell exists in the container.

        Args:
            sandbox_name: The sandbox name.
            shell: The shell path to check.

        Returns:
            True if shell exists, False otherwise.
        """
        container_name = self.container_name(sandbox_name)
        cmd = ["docker", "exec", container_name, "test", "-x", shell]

        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    def exec_shell(self, sandbox_name: str, shell: str = "sh") -> None:
        """Execute an interactive shell in a sandbox container.

        Args:
            sandbox_name: The sandbox name.
            shell: The shell to use (default: sh).

        Raises:
            RuntimeError: If shell doesn't exist in container.
        """
        # Check if shell exists first
        if not self.shell_exists(sandbox_name, shell):
            raise RuntimeError(
                f"Shell '{shell}' not found in container. "
                f"Please add it to your .devcontainer/Dockerfile and rebuild the sandbox:\n"
                f"  1. Add '{shell.split('/')[-1]}' to apt-get install in Dockerfile\n"
                f"  2. Run: agent-sandbox rm {sandbox_name}\n"
                f"  3. Run: agent-sandbox connect {sandbox_name}"
            )

        container_name = self.container_name(sandbox_name)
        cmd = ["docker", "exec", "-it", container_name, shell]

        # Run interactively (replace current process)
        os.execvp("docker", cmd)
