"""Utility functions for agent-sandbox."""

import re
from pathlib import Path
from typing import Optional

import yaml

# Compose file names to search for (in order of preference)
COMPOSE_FILES = [
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
]


def find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find the project root by searching upward for a compose file.
    
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
        for compose_file in COMPOSE_FILES:
            if (current / compose_file).exists():
                return current
        current = current.parent
    
    # Check root directory as well
    for compose_file in COMPOSE_FILES:
        if (current / compose_file).exists():
            return current
    
    return None


def find_compose_file(project_root: Path) -> Optional[Path]:
    """Find the compose file in the project root.
    
    Args:
        project_root: The project root directory.
        
    Returns:
        Path to compose file, or None if not found.
    """
    for compose_file in COMPOSE_FILES:
        path = project_root / compose_file
        if path.exists():
            return path
    return None


def parse_compose_ports(compose_file: Path, service: str) -> list[int]:
    """Parse port mappings from a docker-compose file for a service.
    
    Extracts the container ports (right side of port mapping) from the service.
    Handles formats like:
    - "8000:8000"
    - "${SANDBOX_PORT_0:-8000}:8000"
    - "8000"
    
    Args:
        compose_file: Path to the docker-compose file.
        service: Name of the service to get ports for.
        
    Returns:
        List of container ports (integers).
    """
    try:
        with open(compose_file) as f:
            compose = yaml.safe_load(f)
    except Exception:
        return []
    
    if not compose or "services" not in compose:
        return []
    
    services = compose.get("services", {})
    if service not in services:
        return []
    
    service_config = services[service]
    if not service_config or "ports" not in service_config:
        return []
    
    ports = []
    for port_mapping in service_config["ports"]:
        port_str = str(port_mapping)
        
        # Handle "host:container" format
        if ":" in port_str:
            # Get the container port (right side)
            container_port = port_str.split(":")[-1]
        else:
            # Just a single port
            container_port = port_str
        
        # Extract numeric port (handles env var syntax like ${VAR:-8000})
        # Look for the default value after :- or just the number
        match = re.search(r":-(\d+)", container_port)
        if match:
            ports.append(int(match.group(1)))
        else:
            # Try to parse as plain integer
            try:
                ports.append(int(container_port))
            except ValueError:
                # Skip unparseable ports
                continue
    
    return ports


def extract_sandbox_name(container_name: str) -> str:
    """Extract sandbox name from container name.
    
    Docker Compose creates containers with names like:
    - projectname-service-1
    - projectname_service_1
    
    Args:
        container_name: The full container name.
        
    Returns:
        The extracted sandbox/project name.
    """
    # Remove -dev-1 or _dev_1 suffix
    name = re.sub(r"[-_]dev[-_]\d+$", "", container_name)
    return name
