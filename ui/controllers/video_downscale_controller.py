from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.utils.file_result import FileResult
from src.utils.output_naming import unique_downscale_output_path
from src.utils.progress import ProgressInfo
from src.video.video_directory_downscale import directory_downscaler
from src.video.video_file_downscale import (
    RESOLUTION_PRESETS,
    file_downscaler,
    resolve_target_height,
)
from ui.controllers.base_controller import BaseController, ProgressCallback
from ui.utils.format_utils import video_input_formats

SUPPORTED_VIDEO_DOWNSCALE_PRESETS: tuple[str, ...] = tuple(RESOLUTION_PRESETS.keys())

__all__ = [
    "SUPPORTED_VIDEO_DOWNSCALE_PRESETS",
    "VideoDownscaleController",
]


class VideoDownscaleController(BaseController):
    """Video downscale. ``params`` is the target resolution preset key (e.g. ``"720p"``)."""

    progress_i18n_key = "msg_downscaling_progress"
    show_speed = True
    show_fps = True

    def supported_formats(self) -> list[str]:
        return video_input_formats()

    def build_output_path(self, input_path: Path, output_dir: Path, params: Any) -> Path:
        # Downscaling keeps the original container.
        target_fmt = input_path.suffix.lower().lstrip(".") or "mp4"
        return unique_downscale_output_path(
            input_path=input_path,
            output_dir=output_dir,
            target_height=resolve_target_height(params),
            target_format=target_fmt,
        )

    def run_single_engine(
        self,
        input_path: Path,
        output_path: Path,
        params: Any,
        progress_cb: ProgressCallback,
    ) -> FileResult:
        return file_downscaler(
            input_path=input_path,
            output_path=output_path,
            resolution=params,
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
        return directory_downscaler(
            input_dir=input_dir,
            output_dir=output_dir,
            resolution=params,
            progress_callback=progress_callback,
            cancel_event=self.cancel_event,
        )
