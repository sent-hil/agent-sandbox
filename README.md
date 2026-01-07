# agent-sandbox

A CLI tool that creates isolated development environments for AI coding agents using Docker devcontainers.

## Features

- Creates isolated sandbox environments from your project
- Uses git clones with a local git server for safe experimentation
- Supports Docker devcontainers for consistent environments
- Port forwarding for web applications
- Merge sandbox changes back to your main branch

## Installation

```bash
# Using uv
uv tool install agent-sandbox

# Or install from source
git clone https://github.com/anthropics/agent-sandbox.git
cd agent-sandbox
uv tool install .
```

## Quick Start

```bash
# Initialize devcontainer config (if not present)
agent-sandbox init

# Start a new sandbox
agent-sandbox connect my-sandbox

# List running sandboxes
agent-sandbox ps

# Stop a sandbox
agent-sandbox stop my-sandbox

# Remove a sandbox completely
agent-sandbox rm my-sandbox

# Merge sandbox changes back
agent-sandbox merge my-sandbox
```

## Configuration

Create `agent-sandbox.toml` in your project root or `~/.agent-sandbox.toml` for global settings:

```toml
[defaults]
# Default shell when connecting
shell = "/usr/bin/fish"

[git]
# Git user config for sandbox commits
name = "Your Name"
email = "your.email@example.com"

[shell]
# Commands to run before starting the shell
# Useful for loading environment variables, hooks, etc.
init = [
    # Load direnv for .envrc environment variables
    "command -v direnv >/dev/null && direnv allow && eval \"$(direnv export bash)\" || true",
]

[files]
# Mount files from host into containers
# Format: "source:dest"
mounts = [
    "~/.config/opencode/opencode.json:/root/.config/opencode/opencode.json",
    ".envrc:/workspaces/myproject/.envrc",
]
```

### Shell Init

The `[shell].init` option lets you run commands before the shell starts when connecting to a sandbox. This is useful for:

- Loading environment variables from `.envrc` using direnv
- Setting up SSH agents
- Running custom initialization scripts

The init commands run in bash, then exec into your configured shell with the environment preserved.

## Shell Completion

Enable tab completion for agent-sandbox commands:

```bash
# Bash
eval "$(_AGENT_SANDBOX_COMPLETE=bash_source agent-sandbox)"

# Zsh  
eval "$(_AGENT_SANDBOX_COMPLETE=zsh_source agent-sandbox)"

# Fish
_AGENT_SANDBOX_COMPLETE=fish_source agent-sandbox > ~/.config/fish/completions/agent-sandbox.fish
source ~/.config/fish/completions/agent-sandbox.fish
```

For automatic installation:
```bash
agent-sandbox completion bash --install
agent-sandbox completion zsh --install  
agent-sandbox completion fish --install
```

Auto-detect your current shell:
```bash
agent-sandbox completion
```

## How It Works

1. **Git Server**: Creates a bare git clone (`.git-server/`) as a local "origin"
2. **Sandbox Clone**: Clones from the git server into `.sandboxes/<name>/`
3. **Docker Container**: Builds and runs a container from your devcontainer config
4. **Workspace Mount**: Mounts the sandbox clone into the container

This architecture allows:
- Safe experimentation without affecting your main repo
- Easy merging of changes back to main
- Multiple concurrent sandboxes

## Requirements

- Docker (or Podman)
- Git
- Python 3.10+
