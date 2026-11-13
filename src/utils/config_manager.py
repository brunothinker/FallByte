"""Configuration persistence manager for FallByte using OS-standard directories."""

import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

# Setup module logger
logger = logging.getLogger(__name__)


def get_config_dir() -> Path:
    """Resolves the OS-standard configuration directory for FallByte.

    Uses `%APPDATA%\\FallByte` on Windows and `$XDG_CONFIG_HOME/fallbyte`
    (defaulting to `~/.config/fallbyte`) on Linux and other POSIX systems.

    Returns:
        Path: Absolute path to the platform-appropriate configuration directory.
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "").strip()
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "FallByte"

    xdg_config = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(xdg_config) if xdg_config else Path.home() / ".config"
    return base / "fallbyte"


def _get_legacy_config_file() -> Path:
    """Returns the legacy configuration file path used prior to OS-standard migration."""
    return Path.home() / ".fallbyte" / "config.yaml"


# Resolved configuration paths exposed for startup logging and runtime persistence
CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "theme": "blue_dark",
}


def _parse_yaml_dict(file_path: Path) -> dict[str, Any] | None:
    """Safely reads and parses a YAML mapping from disk without raising exceptions.

    Args:
        file_path (Path): Path to the YAML configuration file.

    Returns:
        dict[str, Any] | None: Parsed dictionary if valid, otherwise None.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data
    except (yaml.YAMLError, OSError) as e:
        logger.error(f"Failed to read configuration file '{file_path}': {e}")
    return None


def _migrate_legacy_config() -> dict[str, Any] | None:
    """Migrates legacy `~/.fallbyte/config.yaml` once if present and valid.

    Strips deprecated keys (such as `theme_mode`) and saves the migrated
    settings to the new OS-standard `CONFIG_FILE` location.

    Returns:
        dict[str, Any] | None: Migrated configuration merged with defaults, or None
        if no legacy file exists or migration fails.
    """
    legacy_file = _get_legacy_config_file()
    if legacy_file == CONFIG_FILE or not legacy_file.exists():
        return None

    legacy_data = _parse_yaml_dict(legacy_file)
    if legacy_data is None:
        return None

    legacy_data.pop("theme_mode", None)
    migrated = DEFAULT_CONFIG.copy()
    migrated.update(legacy_data)

    save_config(migrated)
    logger.info(
        f"Migrated legacy configuration from '{legacy_file}' to '{CONFIG_FILE}'."
    )
    return migrated


def load_config() -> dict[str, Any]:
    """Reads user preferences from the OS-standard YAML configuration file.

    Performs a one-time migration from `~/.fallbyte/config.yaml` when the new
    file does not yet exist. Falls back to `DEFAULT_CONFIG` if missing or corrupted.

    Returns:
        dict[str, Any]: Active user configuration dictionary merged with defaults.
    """
    if not CONFIG_FILE.exists():
        migrated = _migrate_legacy_config()
        if migrated is not None:
            return migrated

        defaults = DEFAULT_CONFIG.copy()
        save_config(defaults)
        return defaults

    parsed = _parse_yaml_dict(CONFIG_FILE)
    if parsed is not None:
        parsed.pop("theme_mode", None)
        merged = DEFAULT_CONFIG.copy()
        merged.update(parsed)
        return merged

    return DEFAULT_CONFIG.copy()


def save_config(config_data: dict[str, Any]) -> None:
    """Atomically persists user preferences dictionary to the local YAML file.

    Writes serialized YAML into a temporary file within `CONFIG_DIR` and moves
    it into `CONFIG_FILE` via `os.replace` to prevent truncated files on crash.

    Args:
        config_data (dict[str, Any]): Configuration key-value mapping to persist.
    """
    tmp_path: Path | None = None
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        clean_data = {k: v for k, v in config_data.items() if k != "theme_mode"}

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CONFIG_DIR,
            prefix=f".{CONFIG_FILE.stem}_tmp_",
            suffix=CONFIG_FILE.suffix,
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            yaml.dump(clean_data, tmp, default_flow_style=False, allow_unicode=True)

        os.replace(tmp_path, CONFIG_FILE)
    except (yaml.YAMLError, OSError) as e:
        logger.error(f"Failed to save configuration file '{CONFIG_FILE}': {e}")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def get_config_value(key: str, default: Any = None) -> Any:
    """Retrieves a single configuration property by key.

    Args:
        key (str): Configuration property key to look up.
        default (Any, optional): Fallback value if key is absent. Defaults to None.

    Returns:
        Any: Stored value associated with `key`, or `default`.
    """
    config = load_config()
    return config.get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """Updates and atomically saves a single configuration property.

    Args:
        key (str): Configuration property key to set.
        value (Any): Value to assign and persist.
    """
    config = load_config()
    config[key] = value
    save_config(config)