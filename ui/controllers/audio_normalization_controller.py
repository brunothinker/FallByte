from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.audio.audio_directory_normalization import directory_normalizer
from src.audio.audio_file_normalization import (
    DEFAULT_LOUDNESS_PRESET,
    NORMALIZABLE_AUDIO_FORMATS,
)
from src.utils.progress import ProgressInfo
from ui.controllers.base_controller import BaseController


def normalizable_audio_formats() -> list[str]:
    """Returns sorted uppercase audio format names supported by loudness normalization."""
    return sorted(fmt.upper() for fmt in NORMALIZABLE_AUDIO_FORMATS)


class AudioNormalizationController(BaseController):
    """Batch loudness normalization. ``params`` is the loudness preset key."""

    progress_i18n_key = "msg_normalizing_progress"
    show_speed = True
    supports_single_file = False

    def supported_formats(self) -> list[str]:
        return normalizable_audio_formats()

    def run_batch_engine(
        self,
        input_dir: Path,
        output_dir: Path,
        params: Any,
        progress_callback: Callable[[ProgressInfo], None],
    ) -> dict[str, Any]:
        return directory_normalizer(
            input_dir=input_dir,
            output_dir=output_dir,
            preset_key=params or DEFAULT_LOUDNESS_PRESET,
            progress_callback=progress_callback,
            cancel_event=self.cancel_event,
        )
