import logging
from pathlib import Path
from typing import Any

import yaml

# Setup module logger
logger = logging.getLogger(__name__)

# Base configuration directory in user home
CONFIG_DIR = Path.home() / ".fallbyte"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "language": "pt",
    "theme_mode": "dark",
}


def load_config() -> dict[str, Any]:
    """Reads user preferences from local YAML configuration file.

    Returns default settings if the file does not exist or fails to parse.
    """
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            if isinstance(config, dict):
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
            return DEFAULT_CONFIG.copy()
    except (yaml.YAMLError, OSError) as e:
        logger.error(f"Failed to load configuration file '{CONFIG_FILE}': {e}")
        return DEFAULT_CONFIG.copy()


def save_config(config_data: dict[str, Any]) -> None:
    """Persists user preferences dictionary to local YAML file."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
    except (yaml.YAMLError, OSError) as e:
        logger.error(f"Failed to save configuration file '{CONFIG_FILE}': {e}")


def get_config_value(key: str, default: Any = None) -> Any:
    """Retrieves a single configuration property by key."""
    config = load_config()
    return config.get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """Updates and saves a single configuration property."""
    config = load_config()
    config[key] = value
    save_config(config)