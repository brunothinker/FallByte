from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.formats import SUPPORTED_VIDEO_EXTENSIONS
from src.utils.output_naming import unique_compression_output_path
from src.utils.progress import ProgressInfo
from src.video.video_directory_compression import directory_compressor
from src.video.video_file_compression import file_compressor
from ui.controllers.base_controller import BaseController, JobUI, ProgressCallback
from ui.utils.format_utils import video_input_formats


class VideoCompressionController(BaseController):
    """Video compression. ``params`` is the quality percentage (int)."""

    progress_i18n_key = "msg_compressing_progress"
    show_speed = True
    show_fps = True

    def supported_formats(self) -> list[str]:
        return video_input_formats()

    def preflight_batch(
        self, ui: JobUI, params: Any, proceed: Callable[[], None]
    ) -> None:
        self._preflight_by_support(
            ui, proceed, lambda f: f.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
        )

    def build_output_path(self, input_path: Path, output_dir: Path, params: Any) -> Path:
        return unique_compression_output_path(
            input_path=input_path, output_dir=output_dir
        )

    def run_single_engine(
        self,
        input_path: Path,
        output_path: Path,
        params: Any,
        progress_cb: ProgressCallback,
    ) -> bool:
        return file_compressor(
            input_path=input_path,
            output_path=output_path,
            quality=int(params),
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
        return directory_compressor(
            input_dir=input_dir,
            output_dir=output_dir,
            quality=int(params),
            progress_callback=progress_callback,
            cancel_event=self.cancel_event,
        )
