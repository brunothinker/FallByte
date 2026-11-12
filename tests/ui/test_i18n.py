"""Unit tests for internationalization (i18n), YAML schema parity, and system language detection."""

import string
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from ui import i18n
from ui.i18n import (
    FALLBACK_LANG,
    TRANSLATIONS,
    _get_locales_dir,
    _load_translations,
    _normalize,
    _read_locale,
    _windows_langid,
    detect_system_language,
    set_language,
    t,
)


def _extract_placeholders(text: str) -> set[tuple[str, str]]:
    """Extracts (field_name, format_spec) tuples from Python format strings."""
    formatter = string.Formatter()
    return {
        (field_name, format_spec or "")
        for _, field_name, format_spec, _ in formatter.parse(text)
        if field_name is not None
    }


def _write_yaml(path: Path, code: str, name: str, strings: dict[str, str]) -> None:
    """Helper to write a structured locale YAML file for isolated tests."""
    payload = {"_meta": {"code": code, "name": name}, "strings": strings}
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# Real Locale Assets & Parity Tests (Issue #55)
# ---------------------------------------------------------------------------


def test_real_locales_match_template_schema() -> None:
    """Ensures all YAML locale files in resources/locales/ are in sync with _template.yaml."""
    locales_dir = _get_locales_dir()
    template = _read_locale(locales_dir / "_template.yaml")
    if template is None:
        pytest.fail("[i18n] Could not load 'resources/locales/_template.yaml'.")

    template_keys = set(template[1].keys())
    if not template_keys:
        pytest.fail("[i18n] 'resources/locales/_template.yaml' has no defined keys.")

    out_of_sync_details: list[str] = []

    for path in sorted(locales_dir.glob("*.yaml")):
        if path.name == "_template.yaml":
            continue

        loaded = _read_locale(path)
        if loaded is None:
            out_of_sync_details.append(f"  - {path.name}: invalid YAML structure")
            continue

        _, strings = loaded
        missing = sorted(template_keys - set(strings.keys()))
        extra = sorted(set(strings.keys()) - template_keys)
        empty = sorted(k for k in template_keys if not strings.get(k, "").strip())

        if missing or extra or empty:
            parts = []
            if missing:
                parts.append(f"missing={missing}")
            if extra:
                parts.append(f"extra={extra}")
            if empty:
                parts.append(f"empty={empty}")
            out_of_sync_details.append(f"  - {path.name}: {', '.join(parts)}")

    if out_of_sync_details:
        details = "\n".join(out_of_sync_details)
        pytest.fail(
            "\n[i18n] Some locale files in 'resources/locales/' are out of sync with '_template.yaml':\n"
            f"{details}\n\n"
            "How to proceed:\n"
            "  1. Either update the outdated locale file(s) with the missing translations, OR\n"
            "  2. If you only added keys for a new feature (in '_template.yaml' and 'en.yaml'),\n"
            "     you can still open your PR — just mention in the PR description which locale(s)\n"
            "     still need translation updates (the app will safely fall back to English).\n"
        )


def test_real_locales_placeholder_parity() -> None:
    """Ensures all format placeholders across loaded languages match the fallback 'en' locale."""
    base_strings = TRANSLATIONS[FALLBACK_LANG]
    mismatches: list[str] = []

    for lang_code, strings in TRANSLATIONS.items():
        if lang_code == FALLBACK_LANG:
            continue
        for key, base_text in base_strings.items():
            expected = _extract_placeholders(base_text)
            actual = _extract_placeholders(strings[key])
            if actual != expected:
                mismatches.append(
                    f"  - {lang_code}.yaml ['{key}']: "
                    f"expected {sorted(expected)}, got {sorted(actual)}"
                )

    if mismatches:
        details = "\n".join(mismatches)
        pytest.fail(
            "\n[i18n] Format placeholder mismatch between locale files and 'en.yaml':\n"
            f"{details}\n\n"
            "Ensure all dynamic placeholders (e.g., {count}, {formats}) match 'en.yaml'.\n"
        )


# ---------------------------------------------------------------------------
# Isolated Loader Validation & Fallback Behavior Tests
# ---------------------------------------------------------------------------


def test_incomplete_secondary_locale_is_skipped_and_falls_back_to_en(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests that an incomplete secondary locale is ignored and set_language falls back to 'en'."""
    _write_yaml(tmp_path / "_template.yaml", "", "", {"greeting": "", "farewell": ""})
    _write_yaml(tmp_path / "en.yaml", "en", "English", {"greeting": "Hello", "farewell": "Bye"})
    _write_yaml(tmp_path / "pt.yaml", "pt", "Português", {"greeting": "Olá"})

    monkeypatch.setattr(i18n, "_get_locales_dir", lambda: tmp_path)
    monkeypatch.setattr(i18n, "TRANSLATIONS", {})
    monkeypatch.setattr(i18n, "AVAILABLE_LANGUAGES", {})
    monkeypatch.setattr(i18n, "CURRENT_LANG", "en")

    _load_translations()

    assert "en" in i18n.TRANSLATIONS, (
        "[i18n] Valid fallback locale 'en' was not loaded into TRANSLATIONS."
    )
    assert "pt" not in i18n.TRANSLATIONS, (
        "[i18n] Incomplete secondary locale 'pt' should have been skipped."
    )
    assert "pt" not in i18n.AVAILABLE_LANGUAGES, (
        "[i18n] Incomplete locale 'pt' must not appear in AVAILABLE_LANGUAGES."
    )

    set_language("pt")
    assert i18n.CURRENT_LANG == "en", (
        "[i18n] Calling set_language('pt') on a skipped locale must fall back to 'en'."
    )
    assert t("greeting") == "Hello", (
        "[i18n] Translation lookup t('greeting') did not return the 'en' fallback value."
    )


def test_out_of_sync_fallback_locale_raises_runtime_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests that out-of-sync en.yaml vs _template.yaml raises RuntimeError on startup."""
    _write_yaml(tmp_path / "_template.yaml", "", "", {"greeting": "", "new_key": ""})
    _write_yaml(tmp_path / "en.yaml", "en", "English", {"greeting": "Hello"})

    monkeypatch.setattr(i18n, "_get_locales_dir", lambda: tmp_path)
    monkeypatch.setattr(i18n, "TRANSLATIONS", {})
    monkeypatch.setattr(i18n, "AVAILABLE_LANGUAGES", {})

    with pytest.raises(
        RuntimeError,
        match="Out of sync",
    ):
        _load_translations()


def test_missing_template_raises_runtime_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests that a missing _template.yaml raises RuntimeError immediately."""
    monkeypatch.setattr(i18n, "_get_locales_dir", lambda: tmp_path)

    with pytest.raises(
        RuntimeError,
        match="_template.yaml",
    ):
        _load_translations()


# ---------------------------------------------------------------------------
# System Locale Detection & Formatting Tests
# ---------------------------------------------------------------------------


def test_normalize_valid_locales(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests normalization of various standard locale string formats into supported codes."""
    monkeypatch.setattr(i18n, "TRANSLATIONS", {"en": {}, "pt": {}, "es": {}})

    cases = [
        ("pt_BR", "pt"),
        ("pt-BR", "pt"),
        ("es_ES.UTF-8", "es"),
        ("en_US", "en"),
        ("Portuguese_Brazil", "pt"),
        ("Spanish_Spain", "es"),
    ]
    for raw_locale, expected in cases:
        actual = _normalize(raw_locale)
        assert actual == expected, (
            f"[i18n] _normalize('{raw_locale}') returned '{actual}', expected '{expected}'."
        )


def test_normalize_invalid_and_empty_locales() -> None:
    """Tests normalization behavior on unsupported, empty, or fallback locale strings."""
    invalid_cases = ["", None, "C", "C.UTF-8", "fr_FR", "ja_JP"]
    for raw_locale in invalid_cases:
        actual = _normalize(raw_locale)
        assert actual is None, (
            f"[i18n] _normalize({raw_locale!r}) returned '{actual}', expected None for unsupported/empty locale."
        )


def test_detect_system_language_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests language detection precedence using mock environment variables."""
    monkeypatch.setattr(i18n, "TRANSLATIONS", {"en": {}, "pt": {}, "es": {}})

    mock_env_pt = {"LANGUAGE": "pt_BR.UTF-8:en"}
    assert detect_system_language(env=mock_env_pt) == "pt", (
        "[i18n] detect_system_language() failed to prioritize primary LANGUAGE='pt_BR.UTF-8:en'."
    )

    mock_env_es = {"LANG": "es_ES.UTF-8"}
    assert detect_system_language(env=mock_env_es) == "es", (
        "[i18n] detect_system_language() failed to detect 'es' from LANG='es_ES.UTF-8'."
    )

    mock_env_unsupported = {"LANG": "fr_FR.UTF-8"}
    assert detect_system_language(env=mock_env_unsupported) == "en", (
        "[i18n] detect_system_language() must fall back to 'en' when LANG is unsupported ('fr_FR.UTF-8')."
    )


def test_detect_system_language_empty_env_fallback() -> None:
    """Tests that an empty environment falls back to 'en' when locale fails."""
    with patch("locale.getlocale", return_value=(None, None)):
        actual = detect_system_language(env={})
        assert actual == "en", (
            f"[i18n] detect_system_language() returned '{actual}' on empty env/locale, expected 'en'."
        )


@patch("sys.platform", "win32")
def test_windows_langid_detection() -> None:
    """Tests Win32 GetUserDefaultUILanguage API parsing via ctypes mock."""
    mock_ctypes = MagicMock()
    # 0x0416 (Portuguese - Brazil), masked with 0x3FF gives 0x16 (pt)
    mock_ctypes.windll.kernel32.GetUserDefaultUILanguage.return_value = 0x0416

    with patch("ctypes.windll", mock_ctypes.windll, create=True):
        lang_id = _windows_langid()
        assert lang_id == 0x16, (
            f"[i18n] _windows_langid() returned {hex(lang_id) if lang_id else lang_id}, expected 0x16 (pt)."
        )


def test_translation_helper_and_formatting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests active language state switching and dynamic parameter formatting."""
    monkeypatch.setattr(i18n, "CURRENT_LANG", "en")

    if "pt" in TRANSLATIONS:
        set_language("pt")
        assert t("nav_home") == "Inicial", (
            "[i18n] t('nav_home') did not return Portuguese translation 'Inicial' after set_language('pt')."
        )

    set_language("en")
    assert t("nav_home") == "Home", (
        "[i18n] t('nav_home') did not return English translation 'Home' after set_language('en')."
    )

    formatted = t("route_not_found", route_key="invalid_path")
    assert "invalid_path" in formatted, (
        f"[i18n] Dynamic placeholder substitution failed in t('route_not_found'): got {formatted!r}."
    )