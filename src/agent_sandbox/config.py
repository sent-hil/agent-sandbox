"""User configuration management for agent-sandbox."""

import sys
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def get_config_path() -> Path:
    """Get the path to the user configuration file.

    Returns:
        Path to ~/.agent-sandbox.toml
    """
    return Path.home() / ".agent-sandbox.toml"


def load_user_config() -> dict:
    """Load user configuration from ~/.agent-sandbox.toml.

    Returns:
        Dict with user configuration, or empty dict if file doesn't exist.
    """
    config_path = get_config_path()

    if not config_path.exists():
        return {}

    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        # Return empty config if file is invalid
        return {}


def get_default_shell() -> Optional[str]:
    """Get the default shell from user configuration.

    Returns:
        Shell path from config, or None if not configured.
    """
    config = load_user_config()
    return config.get("shell")
