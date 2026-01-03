# Agent Guidelines for agent-sandbox

This document provides guidelines for AI coding agents working in this repository.

## Project Overview

`agent-sandbox` is a Python CLI tool that creates isolated development environments for AI coding agents using git worktrees and Docker devcontainers.

### Architecture

```
src/agent_sandbox/
├── cli.py       # Click-based CLI commands (entry point)
├── manager.py   # SandboxManager - main orchestrator
├── docker.py    # DockerClient - container operations
├── git.py       # GitClient - worktree operations
├── utils.py     # Devcontainer parsing utilities
└── init.py      # Default devcontainer template creation
```

## Build & Test Commands

### Package Manager
This project uses `uv` for dependency management.

```bash
# Install dependencies
uv sync

# Install the CLI tool globally
uv tool install .

# Force reinstall after changes (IMPORTANT: clear cache first)
uv cache clean && uv tool install . --force
```

### Linting & Formatting
Run before committing:

```bash
# Check for linting errors
uv run ruff check src/ tests/

# Auto-fix linting errors
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/
```

### Running Tests

```bash
# Run all unit tests
uv run pytest tests/ -v --ignore=tests/e2e

# Run a single test file
uv run pytest tests/test_docker.py -v

# Run a single test class
uv run pytest tests/test_docker.py::TestDockerClientBuildImage -v

# Run a single test method
uv run pytest tests/test_docker.py::TestDockerClientBuildImage::test_builds_image -v

# Run tests matching a pattern
uv run pytest tests/ -v -k "test_builds"

# Run e2e tests (requires Docker running)
uv run pytest tests/e2e/ -v

# Run all tests including e2e
uv run pytest tests/ -v
```

### Test Markers
- `@pytest.mark.e2e` - End-to-end tests requiring Docker

## Code Style Guidelines

Code style is enforced by `ruff`. Run `uv run ruff check --fix` and `uv run ruff format` before committing.

### Type Hints
- Always use type hints for function parameters and return values
- Use `Optional[T]` for nullable parameters
- Use `Path` from pathlib, not string paths
- Define type aliases for complex types

```python
from typing import Callable, Optional
from pathlib import Path

# Type alias for callbacks
ProgressCallback = Callable[[str], None]

def start(
    self,
    name: str,
    branch: Optional[str] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> SandboxInfo:
```

### Naming Conventions
- **Classes**: PascalCase (`SandboxManager`, `DockerClient`)
- **Functions/Methods**: snake_case (`create_worktree`, `get_container_ports`)
- **Variables**: snake_case (`project_root`, `container_name`)
- **Constants**: UPPER_SNAKE_CASE (`SANDBOX_LABEL`, `DEVCONTAINER_PATHS`)
- **Private methods**: prefix with underscore (`_get_next_port_offset`)

### Docstrings
Use Google-style docstrings for all public functions and classes:

```python
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
```

### Error Handling
- Raise `ValueError` for invalid arguments or configuration errors
- Raise `RuntimeError` for external command failures (docker, git)
- Use descriptive error messages

```python
if result.returncode != 0:
    raise RuntimeError(f"docker build failed: {result.stderr}")
```

### Classes
- Use `@dataclass` for simple data containers
- Initialize instance variables in `__init__`
- Prefix private attributes with underscore

```python
@dataclass
class SandboxInfo:
    """Information about a sandbox."""
    name: str
    branch: str
    ports: dict[int, int]
    worktree_path: Path

class SandboxManager:
    def __init__(self, path: Optional[Path] = None):
        self.project_root = find_project_root(path)
        self._docker = DockerClient(self.project_root)
        self._git = GitClient(self.project_root)
```

### Subprocess Calls
- Always use `capture_output=True, text=True` for subprocess calls
- Check `returncode` for success/failure
- Use `result.stderr` for error messages

```python
result = subprocess.run(
    ["docker", "build", "-t", image_name, str(context_path)],
    capture_output=True,
    text=True,
)
if result.returncode != 0:
    raise RuntimeError(f"docker build failed: {result.stderr}")
```

### CLI Commands (Click)
- Use `@main.command()` decorator
- Use `@click.argument()` for required positional args
- Use `@click.option()` for optional flags
- Use Rich console for styled output

```python
@main.command()
@click.argument("name")
@click.option("--shell", "-s", default="/bin/bash", help="Shell to use")
def connect(name: str, shell: str):
    """Connect to a sandbox's shell."""
    with console.status(f"[bold blue]Connecting...", spinner="dots"):
        manager.connect(name, shell)
```

## Testing Guidelines

### Test Structure
- One test file per module (`test_docker.py` for `docker.py`)
- Group related tests in classes (`class TestDockerClientBuildImage`)
- Use descriptive test method names (`test_raises_on_build_failure`)

### Fixtures
- Use `tmp_path` fixture for temporary directories
- Use `pytest-mock` for mocking (`mocker` fixture)
- Define shared fixtures in `conftest.py`

### Mocking External Commands
Mock `subprocess.run` for docker/git commands:

```python
from unittest.mock import MagicMock, patch

def test_builds_image(self, tmp_path):
    client = DockerClient(tmp_path)
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        client.build_image("alice", tmp_path, "Dockerfile")
        
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "build" in call_args
```

## Common Tasks

### Adding a New CLI Command
1. Add the command function in `cli.py` with `@main.command()` decorator
2. Use `get_manager()` to get a `SandboxManager` instance
3. Add progress spinner for long operations using `console.status()`

### Adding Manager Functionality
1. Add method to `SandboxManager` in `manager.py`
2. Delegate to `DockerClient` or `GitClient` as needed
3. Add unit tests mocking the underlying clients

### Modifying the Default Devcontainer
1. Edit `DEFAULT_DOCKERFILE` or `DEFAULT_DEVCONTAINER_JSON` in `init.py`
2. Clear uv cache before reinstalling: `uv cache clean`
