"""Tests ensuring log line coloring depends strictly on LogLevel, never localized text."""

import pytest

from src.utils.file_result import FileResult, LogLevel
from ui.components.dialog_utils import get_log_line_color
from ui.controllers.base_controller import BaseController
from ui.i18n import AVAILABLE_LANGUAGES, set_language, t


@pytest.mark.parametrize(
    ("result", "expected_level"),
    [
        (FileResult.processed(), LogLevel.SUCCESS),
        (FileResult.skipped("skip_not_smaller", quality=80), LogLevel.WARNING),
        (FileResult.failed(), LogLevel.ERROR),
    ],
)
def test_file_result_maps_to_expected_log_level(
    result: FileResult, expected_level: LogLevel
) -> None:
    assert result.log_level is expected_level


@pytest.mark.parametrize(
    "result",
    [
        FileResult.processed(),
        FileResult.skipped("skip_same_format", fmt="png"),
        FileResult.failed(),
    ],
)
def test_same_log_entry_gets_identical_color_across_all_locales(
    result: FileResult,
) -> None:
    colors_by_lang: dict[str, str] = {}

    for lang_code in AVAILABLE_LANGUAGES:
        set_language(lang_code)
        level, formatted_line = BaseController._format_result_entry(
            "video_sucesso_aviso_concluido.mp4", result
        )
        assert formatted_line
        colors_by_lang[lang_code] = get_log_line_color(level)

    set_language("en")
    unique_colors = set(colors_by_lang.values())
    assert len(unique_colors) == 1
    assert unique_colors.pop() == get_log_line_color(result.log_level)


def test_keyword_in_message_text_does_not_override_log_level_color() -> None:
    set_language("pt")
    assert t("msg_success")
    assert get_log_line_color(LogLevel.ERROR) != get_log_line_color(LogLevel.SUCCESS)
    assert get_log_line_color(LogLevel.INFO) != get_log_line_color(LogLevel.WARNING)
    set_language("en")
