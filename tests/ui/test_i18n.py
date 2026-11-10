"""Unit tests for internationalization (i18n) and system language detection modules."""

from unittest.mock import MagicMock, patch

from ui.i18n import (
    _normalize,
    _windows_langid,
    detect_system_language,
    set_language,
    t,
)


def test_normalize_valid_locales() -> None:
    """Tests normalization of various standard locale string formats into supported codes."""
    assert _normalize("pt_BR") == "pt"
    assert _normalize("pt-BR") == "pt"
    assert _normalize("es_ES.UTF-8") == "es"
    assert _normalize("en_US") == "en"
    assert _normalize("Portuguese_Brazil") == "pt"
    assert _normalize("Spanish_Spain") == "es"


def test_normalize_invalid_and_empty_locales() -> None:
    """Tests normalization behavior on unsupported, empty, or fallback locale strings."""
    assert _normalize("") is None
    assert _normalize(None) is None
    assert _normalize("C") is None
    assert _normalize("C.UTF-8") is None
    assert _normalize("fr_FR") is None
    assert _normalize("ja_JP") is None


def test_detect_system_language_environment_variables() -> None:
    """Tests language detection precedence using mock environment variables."""
    # Test matching primary LANGUAGE variable
    mock_env_pt = {"LANGUAGE": "pt_BR.UTF-8:en"}
    assert detect_system_language(env=mock_env_pt) == "pt"

    # Test fallback to LANG when higher precedence vars are absent
    mock_env_es = {"LANG": "es_ES.UTF-8"}
    assert detect_system_language(env=mock_env_es) == "es"

    # Test unsupported language falls back to 'en'
    mock_env_unsupported = {"LANG": "fr_FR.UTF-8"}
    assert detect_system_language(env=mock_env_unsupported) == "en"


def test_detect_system_language_empty_env_fallback() -> None:
    """Tests that an empty environment falls back to 'en' when locale fails."""
    with patch("locale.getlocale", return_value=(None, None)):
        assert detect_system_language(env={}) == "en"


@patch("sys.platform", "win32")
def test_windows_langid_detection() -> None:
    """Tests Win32 GetUserDefaultUILanguage API parsing via ctypes mock."""
    mock_ctypes = MagicMock()
    # 0x0416 (Portuguese - Brazil), masked with 0x3FF gives 0x16 (pt)
    mock_ctypes.windll.kernel32.GetUserDefaultUILanguage.return_value = 0x0416

    with patch("ctypes.windll", mock_ctypes.windll, create=True):
        assert _windows_langid() == 0x16


def test_translation_helper_and_formatting() -> None:
    """Tests active language state switching and dynamic parameter formatting."""
    set_language("pt")
    assert t("nav_home") == "Inicial"

    set_language("en")
    assert t("nav_home") == "Home"

    # Test dynamic string formatting placeholder
    formatted = t("route_not_found", route_key="invalid_path")
    assert "invalid_path" in formatted