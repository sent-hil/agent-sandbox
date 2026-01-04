# Agent Guidelines for agent-sandbox

## Project Overview

Python CLI tool that creates isolated development environments using Docker devcontainers.

### Architecture

```
src/agent_sandbox/
├── cli.py       # Click CLI commands (entry point)
├── config.py    # TOML configuration loading
├── manager.py   # SandboxManager - main orchestrator
├── docker.py    # DockerClient - container operations
├── git.py       # GitClient - git server and sandbox clones
├── utils.py     # Devcontainer JSON parsing
└── init.py      # Default devcontainer template
```

## Commands

```bash
# Install/reinstall CLI (IMPORTANT: clear cache first)
uv cache clean && uv tool install . --force

# Lint and format (run before committing)
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/

# Run unit tests
uv run pytest tests/ -v --ignore=tests/e2e

# Run e2e tests (requires Docker)
uv run pytest tests/e2e/ -v

# Quick test cycle (rebuild CLI and test sandbox)
./test-sandbox.sh
```

## Code Style

- Enforced by `ruff` - run check and format before committing
- Type hints required for all function parameters and return values
- Use `Path` from pathlib, not string paths
- Google-style docstrings for public functions
- Raise `ValueError` for bad input, `RuntimeError` for external command failures

## Testing

- One test file per module (`test_docker.py` for `docker.py`)
- Group tests in classes (`class TestDockerClientBuildImage`)
- Mock `subprocess.run` for docker/git commands
- Use `tmp_path` fixture for temporary directories

## Common Tasks

**Adding a CLI command**: Add function in `cli.py` with `@main.command()` decorator

**Adding config option**: Add getter in `config.py`, use in relevant module

**Modifying default devcontainer**: Edit templates in `init.py`, then `uv cache clean`
