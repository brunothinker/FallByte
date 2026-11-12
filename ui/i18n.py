"""Internationalization (i18n) module for multi-language support.

Provides translation lookup helpers, active language state management,
and system locale/language auto-detection for cross-platform operations.
"""

import locale
import logging
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

# Setup module logger
logger = logging.getLogger(__name__)

# Default and fallback language identifier
FALLBACK_LANG: str = "en"

# Active language identifier
CURRENT_LANG: str = FALLBACK_LANG

# Centralized translation dictionary populated from resources/locales/*.yaml
TRANSLATIONS: dict[str, dict[str, str]] = {}

# Display names for the language selector UI
AVAILABLE_LANGUAGES: dict[str, str] = {}

# Auxiliary mapping for Windows localized language names to supported ISO codes
_WIN_NAMES: dict[str, str] = {
    "portuguese": "pt",
    "spanish": "es",
    "english": "en",
}

# Win32 primary language identifiers (GetUserDefaultUILanguage & 0x3FF)
_WIN_LANGIDS: dict[int, str] = {
    0x16: "pt",
    0x0A: "es",
    0x09: "en",
}


def _get_locales_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    base = Path(meipass) if meipass else Path(__file__).resolve().parent.parent
    return base / "resources" / "locales"


def _read_locale(path: Path) -> tuple[dict[str, str], dict[str, str]] | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("_meta"), dict)
            or not isinstance(data.get("strings"), dict)
        ):
            return None
        meta = {str(k): str(v or "") for k, v in data["_meta"].items()}
        strings = {str(k): str(v or "") for k, v in data["strings"].items()}
        return meta, strings
    except (OSError, yaml.YAMLError) as e:
        logger.error(f"Failed to load locale file '{path.name}': {e}")
        return None


def _load_translations() -> None:
    locales_dir = _get_locales_dir()
    template = _read_locale(locales_dir / "_template.yaml")
    if not template:
        raise RuntimeError(
            "[i18n ERROR] Failed to load '_template.yaml'. Application cannot start without a valid locale template."
        )

    required_keys = set(template[1].keys())

    for path in sorted(locales_dir.glob("*.yaml")):
        if path.name == "_template.yaml":
            continue

        loaded = _read_locale(path)
        if not loaded:
            continue

        meta, strings = loaded
        code = meta.get("code", "").strip() or path.stem
        missing = required_keys - set(strings.keys())
        extra = set(strings.keys()) - required_keys
        empty = {k for k in required_keys if not strings.get(k, "").strip()}

        if missing or extra or empty:
            logger.warning(
                f"Locale '{code}' skipped (missing={sorted(missing)}, "
                f"extra={sorted(extra)}, empty={sorted(empty)})."
            )
            continue

        TRANSLATIONS[code] = strings
        AVAILABLE_LANGUAGES[code] = meta.get("name") or code

    if FALLBACK_LANG not in TRANSLATIONS:
        raise RuntimeError(
            f"[i18n ERROR] Out of sync: development locale '{FALLBACK_LANG}.yaml' "
            "does not match '_template.yaml'. Check missing, extra, or empty keys."
        )


def t(key: str, **kwargs: Any) -> str:
    """Translates a key into active language, replacing dynamic placeholders."""
    lang_map = TRANSLATIONS.get(CURRENT_LANG, {})
    text = lang_map.get(key) or TRANSLATIONS.get(FALLBACK_LANG, {}).get(key) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError as e:
            logger.warning(
                f"Missing placeholder variable {e} when formatting translation key '{key}'."
            )
    return text


def set_language(lang_code: str) -> None:
    """Sets active language code for translation helper, falling back to 'en' if unavailable."""
    global CURRENT_LANG
    if lang_code in TRANSLATIONS:
        CURRENT_LANG = lang_code
    else:
        logger.warning(
            f"Attempted to set unsupported or incomplete language code '{lang_code}'. "
            f"Falling back to '{FALLBACK_LANG}'."
        )
        CURRENT_LANG = FALLBACK_LANG


def _normalize(raw: str | None) -> str | None:
    if not raw:
        return None
    token = re.split(r"[_\-.@:]", raw.strip().lower())[0]
    code = _WIN_NAMES.get(token, token)
    return code if code in TRANSLATIONS else None


def _windows_langid() -> int | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        windll = getattr(ctypes, "windll", None)
        if windll:
            return windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
    except (AttributeError, OSError):
        return None
    return None


def detect_system_language(env: Mapping[str, str] | None = None) -> str:
    """Detects system language code, falling back to 'en' if unsupported."""
    use_process_state = env is None
    env_map = os.environ if env is None else env

    if use_process_state and sys.platform == "win32":
        langid = _windows_langid()
        if langid in _WIN_LANGIDS and _WIN_LANGIDS[langid] in TRANSLATIONS:
            return _WIN_LANGIDS[langid]

    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        env_val = env_map.get(var) or ""
        for part in env_val.split(":"):
            code = _normalize(part)
            if code:
                return code

    if use_process_state:
        try:
            loc_tuple = locale.getlocale()
            if loc_tuple and loc_tuple[0]:
                code = _normalize(loc_tuple[0])
                if code:
                    return code
        except (ValueError, locale.Error) as e:
            logger.warning(f"Failed to query system locale: {e}")

    return FALLBACK_LANG


_load_translations()