"""Unit tests for OS-standard configuration paths, legacy migration, and atomic writes."""

from pathlib import Path

import pytest
import yaml

from src.utils import config_manager


@pytest.fixture
def patched_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolates home directory and platform environment variables per test."""
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    return fake_home


def _bind_resolved_paths(monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Recomputes and binds CONFIG_DIR and CONFIG_FILE for the mocked platform/env."""
    cfg_dir = config_manager.get_config_dir()
    cfg_file = cfg_dir / "config.yaml"
    monkeypatch.setattr(config_manager, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", cfg_file)
    return cfg_dir, cfg_file


# ---------------------------------------------------------------------------
# OS-Standard Directory Resolution Tests
# ---------------------------------------------------------------------------


def test_linux_default_config_dir(
    patched_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolves `~/.config/fallbyte` on Linux when XDG_CONFIG_HOME is unset."""
    monkeypatch.setattr(config_manager.sys, "platform", "linux")

    expected = patched_env / ".config" / "fallbyte"
    resolved = config_manager.get_config_dir()
    assert resolved == expected, (
        f"Linux default configuration directory changed! Expected '{expected}', "
        f"got '{resolved}'. Check `get_config_dir()` POSIX fallback logic."
    )


def test_linux_xdg_config_home_respected(
    patched_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolves `$XDG_CONFIG_HOME/fallbyte` on Linux when XDG_CONFIG_HOME is defined."""
    monkeypatch.setattr(config_manager.sys, "platform", "linux")
    custom_xdg = tmp_path / "custom_xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(custom_xdg))

    expected = custom_xdg / "fallbyte"
    resolved = config_manager.get_config_dir()
    assert resolved == expected, (
        f"XDG_CONFIG_HOME environment variable was ignored on Linux! Expected '{expected}', "
        f"got '{resolved}'. Check `os.environ.get('XDG_CONFIG_HOME')` handling in `get_config_dir()`."
    )


def test_windows_appdata_config_dir(
    patched_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolves `%APPDATA%\\FallByte` on Windows."""
    monkeypatch.setattr(config_manager.sys, "platform", "win32")
    fake_appdata = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("APPDATA", str(fake_appdata))

    expected = fake_appdata / "FallByte"
    resolved = config_manager.get_config_dir()
    assert resolved == expected, (
        f"Windows configuration directory changed or ignored %APPDATA%! Expected '{expected}', "
        f"got '{resolved}'. Check `win32` branch and `APPDATA` resolution in `get_config_dir()`."
    )


def test_windows_fallback_without_appdata_env(
    patched_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falls back to `~/AppData/Roaming/FallByte` on Windows if APPDATA is unset."""
    monkeypatch.setattr(config_manager.sys, "platform", "win32")

    expected = patched_env / "AppData" / "Roaming" / "FallByte"
    resolved = config_manager.get_config_dir()
    assert resolved == expected, (
        f"Windows fallback directory changed when APPDATA is missing! Expected '{expected}', "
        f"got '{resolved}'. Check the `AppData/Roaming` fallback path in `get_config_dir()`."
    )


# ---------------------------------------------------------------------------
# Legacy Migration Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform_name", ["linux", "win32"])
def test_migrates_legacy_config_once_on_both_platforms(
    patched_env: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform_name: str,
) -> None:
    """Migrates `~/.fallbyte/config.yaml` once into the new location and strips `theme_mode`."""
    monkeypatch.setattr(config_manager.sys, "platform", platform_name)
    if platform_name == "win32":
        monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))

    _, new_file = _bind_resolved_paths(monkeypatch)

    legacy_dir = patched_env / ".fallbyte"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_file = legacy_dir / "config.yaml"
    legacy_file.write_text(
        yaml.safe_dump(
            {
                "theme_mode": "light",
                "theme": "emerald_light",
                "language": "pt",
            }
        ),
        encoding="utf-8",
    )

    loaded = config_manager.load_config()

    assert new_file.exists(), (
        f"Legacy configuration file '{legacy_file}' was not migrated to '{new_file}' "
        f"on platform '{platform_name}'. Check `_migrate_legacy_config()` in `load_config()`."
    )
    assert loaded == {"theme": "emerald_light", "language": "pt"}, (
        f"Migrated preferences were lost or altered! Expected {{'theme': 'emerald_light', 'language': 'pt'}}, "
        f"got {loaded}. Ensure existing keys like `theme` and `language` are preserved during migration."
    )
    assert "theme_mode" not in loaded, (
        "Deprecated `theme_mode` key leaked into migrated config! "
        "Ensure `_migrate_legacy_config()` strips obsolete keys."
    )

    persisted = yaml.safe_load(new_file.read_text(encoding="utf-8"))
    assert persisted == {"theme": "emerald_light", "language": "pt"}, (
        f"Migrated config on disk at '{new_file}' does not match expected values. "
        f"Got {persisted} on disk."
    )

    # Mutate legacy file afterwards to confirm migration only happens once
    legacy_file.write_text(
        yaml.safe_dump({"theme": "red_dark", "language": "es"}),
        encoding="utf-8",
    )
    second_load = config_manager.load_config()
    assert second_load["theme"] == "emerald_light" and second_load["language"] == "pt", (
        "Legacy config was re-read after the new config file already existed! "
        "Migration must run only once when `CONFIG_FILE` is absent."
    )


def test_fresh_install_writes_default_config_without_theme_mode(
    patched_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Creates default config without `theme_mode` when neither new nor legacy files exist."""
    monkeypatch.setattr(config_manager.sys, "platform", "linux")
    _, new_file = _bind_resolved_paths(monkeypatch)

    loaded = config_manager.load_config()

    assert new_file.exists(), (
        f"Fresh startup did not create the default configuration file at '{new_file}'. "
        "Check `load_config()` initialization path."
    )
    assert loaded == {"theme": "blue_dark"}, (
        f"Default configuration keys changed! Expected {{'theme': 'blue_dark'}}, got {loaded}. "
        "Check `DEFAULT_CONFIG` definition."
    )
    assert "theme_mode" not in loaded, (
        "Orphaned `theme_mode` key is still present in `DEFAULT_CONFIG`. "
        "Remove it since theme mode is inferred from the theme suffix."
    )


# ---------------------------------------------------------------------------
# Atomic Write & Corrupted YAML Resilience Tests
# ---------------------------------------------------------------------------


def test_save_config_is_atomic_and_leaves_no_temp_files(
    patched_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures `save_config` uses atomic replace and cleans up temporary artifacts."""
    monkeypatch.setattr(config_manager.sys, "platform", "linux")
    cfg_dir, cfg_file = _bind_resolved_paths(monkeypatch)

    config_manager.save_config({"theme": "purple_dark", "language": "es"})

    assert cfg_file.exists(), (
        f"`save_config()` failed to commit configuration to '{cfg_file}'. "
        "Verify `os.replace()` target path."
    )
    leftover_tmps = list(cfg_dir.glob(".*_tmp_*"))
    assert leftover_tmps == [], (
        f"Temporary files were left behind in '{cfg_dir}' after `save_config()`: {leftover_tmps}. "
        "Ensure `os.replace()` moves the temp file atomically without leaving artifacts."
    )
    saved_data = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert saved_data == {"theme": "purple_dark", "language": "es"}, (
        f"Saved YAML content at '{cfg_file}' does not match input data. Got {saved_data}."
    )


def test_save_config_preserves_existing_file_on_write_failure(
    patched_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures failed writes do not corrupt existing configuration or leave temp files."""
    monkeypatch.setattr(config_manager.sys, "platform", "linux")
    cfg_dir, cfg_file = _bind_resolved_paths(monkeypatch)

    config_manager.save_config({"theme": "amber_dark", "language": "pt"})
    original_content = cfg_file.read_text(encoding="utf-8")

    def failing_dump(*_args, **_kwargs) -> None:
        raise OSError("Simulated disk write interruption")

    monkeypatch.setattr(config_manager.yaml, "dump", failing_dump)

    config_manager.save_config({"theme": "red_light", "language": "en"})

    assert cfg_file.exists(), (
        f"Existing configuration file '{cfg_file}' was deleted after a failed write! "
        "Atomic writes must preserve the previous valid file on error."
    )
    assert cfg_file.read_text(encoding="utf-8") == original_content, (
        f"Existing configuration file '{cfg_file}' was truncated or corrupted when `yaml.dump` failed! "
        "Ensure serialization writes to a temporary file before calling `os.replace()`."
    )
    leftover_tmps = list(cfg_dir.glob(".*_tmp_*"))
    assert leftover_tmps == [], (
        f"Failed `save_config()` leaked temporary files in '{cfg_dir}': {leftover_tmps}. "
        "Ensure the `except` block unlinks `tmp_path` on failure."
    )


def test_corrupted_yaml_falls_back_to_defaults_without_raising(
    patched_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensures malformed YAML content falls back cleanly to `DEFAULT_CONFIG`."""
    monkeypatch.setattr(config_manager.sys, "platform", "linux")
    cfg_dir, cfg_file = _bind_resolved_paths(monkeypatch)
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(":::invalid_yaml: [\n\tbroken", encoding="utf-8")

    loaded = config_manager.load_config()

    assert loaded == {"theme": "blue_dark"}, (
        f"Corrupted YAML at '{cfg_file}' did not fall back to `DEFAULT_CONFIG`! "
        f"Got {loaded}. Check `yaml.YAMLError` handling in `load_config()`."
    )
    assert "theme_mode" not in loaded, (
        "Corrupted YAML fallback reintroduced the deprecated `theme_mode` key."
    )