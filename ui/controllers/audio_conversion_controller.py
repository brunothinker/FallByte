from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.audio.audio_directory_conversion import directory_converter
from src.audio.audio_file_conversion import file_converter
from src.formats import (
    AUDIO_TARGET_FORMATS as SUPPORTED_AUDIO_CONVERSION_FORMATS,
)
from src.utils.file_result import FileResult
from src.utils.output_naming import unique_conversion_output_path
from src.utils.progress import ProgressInfo
from ui.controllers.base_controller import BaseController, ProgressCallback
from ui.utils.format_utils import audio_input_formats

__all__ = [
    "SUPPORTED_AUDIO_CONVERSION_FORMATS",
    "AudioConversionController",
]


class AudioConversionController(BaseController):
    """Audio conversion. ``params`` is the target format string (e.g. ``"MP3"``)."""

    progress_i18n_key = "msg_converting_progress"
    show_speed = True

    def supported_formats(self) -> list[str]:
        return audio_input_formats()

    def build_output_path(self, input_path: Path, output_dir: Path, params: Any) -> Path:
        return unique_conversion_output_path(
            input_path=input_path,
            output_dir=output_dir,
            target_format=str(params).lower(),
        )

    def run_single_engine(
        self,
        input_path: Path,
        output_path: Path,
        params: Any,
        progress_cb: ProgressCallback,
    ) -> FileResult:
        return file_converter(
            input_path=input_path,
            output_path=output_path,
            target_format=str(params).lower(),
            cancel_event=self.cancel_event,
            file_progress_callback=progress_cb,
        )

    def run_batch_engine(
        self,
        input_dir: Path,
        output_dir: Path,
        params: Any,
        progress_callback: Callable[[ProgressInfo], None],
    ) -> dict[str, Any]:
        return directory_converter(
            input_dir=input_dir,
            output_dir=output_dir,
            target_format=str(params).lower(),
            progress_callback=progress_callback,
            cancel_event=self.cancel_event,
        )
