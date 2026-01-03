"""Utility functions for agent-sandbox."""

import json
import re
from pathlib import Path
from typing import Optional

# Devcontainer file locations to search for (in order of preference)
DEVCONTAINER_PATHS = [
    ".devcontainer/devcontainer.json",
    ".devcontainer.json",
]


def find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find the project root by searching upward for a devcontainer.json.
    
    Args:
        start_path: Directory to start searching from. Defaults to current directory.
        
    Returns:
        Path to project root, or None if not found.
    """
    if start_path is None:
        start_path = Path.cwd()
    
    start_path = Path(start_path).resolve()
    current = start_path
    
    # Walk up the directory tree
    while current != current.parent:
        for devcontainer_path in DEVCONTAINER_PATHS:
            if (current / devcontainer_path).exists():
                return current
        current = current.parent
    
    # Check root directory as well
    for devcontainer_path in DEVCONTAINER_PATHS:
        if (current / devcontainer_path).exists():
            return current
    
    return None


def find_devcontainer_json(project_root: Path) -> Optional[Path]:
    """Find the devcontainer.json file in the project.
    
    Args:
        project_root: The project root directory.
        
    Returns:
        Path to devcontainer.json, or None if not found.
    """
    for devcontainer_path in DEVCONTAINER_PATHS:
        path = project_root / devcontainer_path
        if path.exists():
            return path
    return None


def parse_devcontainer_json(devcontainer_file: Path) -> dict:
    """Parse devcontainer.json file.
    
    Handles JSON with comments (jsonc) by stripping them.
    
    Args:
        devcontainer_file: Path to devcontainer.json.
        
    Returns:
        Parsed devcontainer configuration dict.
    """
    content = devcontainer_file.read_text()
    
    # Strip single-line comments (// ...)
    content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
    # Strip multi-line comments (/* ... */)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def parse_devcontainer_ports(devcontainer_file: Path) -> list[int]:
    """Parse forwarded ports from a devcontainer.json file.
    
    Extracts ports from the forwardPorts array.
    
    Args:
        devcontainer_file: Path to the devcontainer.json file.
        
    Returns:
        List of ports (integers).
    """
    config = parse_devcontainer_json(devcontainer_file)
    
    if not config:
        return []
    
    # Get forwardPorts array
    forward_ports = config.get("forwardPorts", [])
    
    ports = []
    for port in forward_ports:
        if isinstance(port, int):
            ports.append(port)
        elif isinstance(port, str):
            # Handle string port (e.g., "8000")
            try:
                ports.append(int(port))
            except ValueError:
                continue
    
    return ports


def get_devcontainer_build_context(devcontainer_file: Path) -> tuple[Path, str]:
    """Get the build context and Dockerfile for a devcontainer.
    
    Args:
        devcontainer_file: Path to devcontainer.json.
        
    Returns:
        Tuple of (context_path, dockerfile_path relative to context).
    """
    config = parse_devcontainer_json(devcontainer_file)
    devcontainer_dir = devcontainer_file.parent
    
    # Check for build configuration
    build_config = config.get("build", {})
    
    if build_config:
        # Has build config
        context = build_config.get("context", ".")
        dockerfile = build_config.get("dockerfile", "Dockerfile")
        
        # Context is relative to devcontainer.json location
        context_path = (devcontainer_dir / context).resolve()
        
        return context_path, dockerfile
    
    # Check for dockerFile (legacy) or dockerfile at root
    dockerfile = config.get("dockerFile") or config.get("dockerfile")
    if dockerfile:
        # Dockerfile is relative to devcontainer.json
        return devcontainer_dir, dockerfile
    
    # Check for image (no build needed)
    if config.get("image"):
        return devcontainer_dir, ""
    
    # Default: look for Dockerfile in .devcontainer/
    if (devcontainer_dir / "Dockerfile").exists():
        return devcontainer_dir, "Dockerfile"
    
    return devcontainer_dir, ""


def get_devcontainer_image(devcontainer_file: Path) -> Optional[str]:
    """Get the base image from devcontainer.json if specified.
    
    Args:
        devcontainer_file: Path to devcontainer.json.
        
    Returns:
        Image name or None if build is configured instead.
    """
    config = parse_devcontainer_json(devcontainer_file)
    return config.get("image")


def get_devcontainer_workdir(devcontainer_file: Path) -> str:
    """Get the working directory from devcontainer.json.
    
    Args:
        devcontainer_file: Path to devcontainer.json.
        
    Returns:
        Working directory path (default: /workspaces/<project_name>).
    """
    config = parse_devcontainer_json(devcontainer_file)
    
    # Check for workspaceFolder
    workspace_folder = config.get("workspaceFolder")
    if workspace_folder:
        return workspace_folder
    
    # Default devcontainer convention
    return "/workspaces/project"


def extract_sandbox_name(container_name: str) -> str:
    """Extract sandbox name from container name.
    
    Container names follow pattern: sandbox-<name>
    
    Args:
        container_name: The full container name.
        
    Returns:
        The extracted sandbox name.
    """
    # Remove sandbox- prefix if present
    if container_name.startswith("sandbox-"):
        return container_name[8:]
    return container_name
