from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.formats import (
    VIDEO_TARGET_FORMATS as SUPPORTED_VIDEO_CONVERSION_FORMATS,
)
from src.utils.file_result import FileResult
from src.utils.output_naming import unique_conversion_output_path
from src.utils.progress import ProgressInfo
from src.video.video_directory_conversion import directory_converter
from src.video.video_file_conversion import file_converter
from ui.controllers.base_controller import BaseController, ProgressCallback
from ui.utils.format_utils import video_input_formats

__all__ = [
    "SUPPORTED_VIDEO_CONVERSION_FORMATS",
    "VideoConversionController",
]


class VideoConversionController(BaseController):
    """Video conversion. ``params`` is the target format string (e.g. ``"MP4"``)."""

    progress_i18n_key = "msg_converting_progress"
    show_speed = True
    show_fps = True

    def supported_formats(self) -> list[str]:
        return video_input_formats()

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
