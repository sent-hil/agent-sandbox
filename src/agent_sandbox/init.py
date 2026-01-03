"""Initialize devcontainer configuration for agent-sandbox."""

import subprocess
from pathlib import Path
from typing import Optional

# Default Dockerfile for agent sandboxes
# Includes common tools needed for Claude Code and OpenCode
DEFAULT_DOCKERFILE = '''FROM ubuntu:24.04

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install essential tools
RUN apt-get update && apt-get install -y \\
    curl \\
    git \\
    sudo \\
    wget \\
    unzip \\
    build-essential \\
    ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for Claude Code and other JS tools)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \\
    && apt-get install -y nodejs \\
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create a non-root user
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \\
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \\
    && echo $USERNAME ALL=\\(root\\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \\
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Set the default user
USER $USERNAME
WORKDIR /home/$USERNAME

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Keep container running
CMD ["sleep", "infinity"]
'''

# Default devcontainer.json
DEFAULT_DEVCONTAINER_JSON = '''{
    "name": "Agent Sandbox",
    "build": {
        "dockerfile": "Dockerfile"
    },
    "forwardPorts": [],
    "workspaceFolder": "/workspaces/${PROJECT_NAME}",
    "remoteUser": "dev",
    "customizations": {
        "vscode": {
            "extensions": []
        }
    }
}
'''


def find_git_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find the root of the git repository.
    
    Args:
        start_path: Path to start searching from. Defaults to cwd.
        
    Returns:
        Path to git root, or None if not in a git repo.
    """
    if start_path is None:
        start_path = Path.cwd()
    
    start_path = Path(start_path).resolve()
    
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start_path,
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        return None
    
    return Path(result.stdout.strip())


def create_devcontainer(
    project_root: Path,
    project_name: Optional[str] = None,
) -> None:
    """Create a devcontainer configuration for agent-sandbox.
    
    Args:
        project_root: Root directory of the project.
        project_name: Name for the project (default: directory name).
    """
    if project_name is None:
        project_name = project_root.name
    
    devcontainer_dir = project_root / ".devcontainer"
    devcontainer_dir.mkdir(exist_ok=True)
    
    # Create Dockerfile
    dockerfile_path = devcontainer_dir / "Dockerfile"
    dockerfile_path.write_text(DEFAULT_DOCKERFILE)
    
    # Create devcontainer.json with project name substituted
    devcontainer_json = DEFAULT_DEVCONTAINER_JSON.replace("${PROJECT_NAME}", project_name)
    devcontainer_json_path = devcontainer_dir / "devcontainer.json"
    devcontainer_json_path.write_text(devcontainer_json)
