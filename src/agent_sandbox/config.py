"""Configuration management for agent-sandbox."""

import sys
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# Config file names to search for (in order of priority)
PROJECT_CONFIG_NAMES = ["agent-sandbox.toml", ".agent-sandbox.toml"]


def find_project_config() -> Optional[Path]:
    """Find project-level config file by searching up from cwd.

    Returns:
        Path to config file, or None if not found.
    """
    current = Path.cwd().resolve()

    while current != current.parent:
        for name in PROJECT_CONFIG_NAMES:
            config_path = current / name
            if config_path.exists():
                return config_path
        current = current.parent

    # Check root directory
    for name in PROJECT_CONFIG_NAMES:
        config_path = current / name
        if config_path.exists():
            return config_path

    return None


def get_user_config_path() -> Path:
    """Get the path to the user configuration file.

    Returns:
        Path to ~/.agent-sandbox.toml
    """
    return Path.home() / ".agent-sandbox.toml"


def load_config_file(config_path: Path) -> dict:
    """Load a TOML config file.

    Args:
        config_path: Path to the config file.

    Returns:
        Dict with configuration, or empty dict if file is invalid.
    """
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def load_config() -> dict:
    """Load configuration with project config taking priority over user config.

    Search order:
    1. Project config (agent-sandbox.toml or .agent-sandbox.toml in cwd or parents)
    2. User config (~/.agent-sandbox.toml)

    Returns:
        Merged configuration dict.
    """
    config: dict = {}

    # Load user config first (lower priority)
    user_config_path = get_user_config_path()
    if user_config_path.exists():
        config = load_config_file(user_config_path)

    # Load project config (higher priority, overrides user config)
    project_config_path = find_project_config()
    if project_config_path:
        project_config = load_config_file(project_config_path)
        # Merge: project config overrides user config
        config = {**config, **project_config}

    return config


def get_default_shell() -> Optional[str]:
    """Get the default shell from configuration.

    Checks multiple locations in order:
    1. [sandbox].default_shell
    2. [defaults].shell
    3. Top-level 'shell'

    Returns:
        Shell path from config, or None if not configured.
    """
    config = load_config()

    # Check [sandbox].default_shell
    sandbox_config = config.get("sandbox", {})
    if isinstance(sandbox_config, dict) and "default_shell" in sandbox_config:
        return sandbox_config["default_shell"]

    # Check [defaults].shell
    defaults_config = config.get("defaults", {})
    if isinstance(defaults_config, dict) and "shell" in defaults_config:
        return defaults_config["shell"]

    # Fall back to top-level 'shell'
    return config.get("shell")


def get_git_name() -> Optional[str]:
    """Get the git user name from configuration.

    Returns:
        Git user name from config, or None if not configured.
    """
    config = load_config()
    git_config = config.get("git", {})
    if isinstance(git_config, dict):
        return git_config.get("name")
    return None


def get_git_email() -> Optional[str]:
    """Get the git user email from configuration.

    Returns:
        Git user email from config, or None if not configured.
    """
    config = load_config()
    git_config = config.get("git", {})
    if isinstance(git_config, dict):
        return git_config.get("email")
    return None


def get_mounts(project_root: Optional[Path] = None) -> list[tuple[str, str]]:
    """Get file mounts from configuration.

    Mounts are specified as "source:dest" strings in [files].mounts array.
    Source paths support ~ expansion and relative paths (resolved from project root).

    Args:
        project_root: Project root for resolving relative paths. Defaults to cwd.

    Returns:
        List of (source, dest) tuples with absolute source paths.
    """
    config = load_config()
    files_config = config.get("files", {})

    if not isinstance(files_config, dict):
        return []

    mounts_list = files_config.get("mounts", [])

    if not isinstance(mounts_list, list):
        return []

    if project_root is None:
        project_root = Path.cwd()

    mounts = []
    for mount in mounts_list:
        if not isinstance(mount, str):
            continue
        if ":" not in mount:
            continue

        # Split on first colon only (dest paths might have colons on Windows)
        source, dest = mount.split(":", 1)

        # Expand ~ and resolve relative paths
        source_path = Path(source).expanduser()
        if not source_path.is_absolute():
            source_path = project_root / source_path
        source = str(source_path.resolve())

        mounts.append((source, dest))

    return mounts
