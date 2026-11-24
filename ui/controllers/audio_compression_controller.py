from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.audio.audio_directory_compression import directory_compressor
from src.audio.audio_file_compression import file_compressor
from src.formats import SUPPORTED_AUDIO_EXTENSIONS, UNCOMPRESSIBLE_AUDIO_FORMATS
from src.utils.file_result import FileResult
from src.utils.output_naming import unique_compression_output_path
from src.utils.progress import ProgressInfo
from ui.controllers.base_controller import BaseController, JobUI, ProgressCallback
from ui.utils.format_utils import audio_compression_formats


class AudioCompressionController(BaseController):
    """Audio compression. ``params`` is the quality percentage (int)."""

    progress_i18n_key = "msg_compressing_progress"
    show_speed = True

    _COMPRESSIBLE_EXTS = frozenset(
        ext
        for ext in SUPPORTED_AUDIO_EXTENSIONS
        if ext.lstrip(".").upper() not in UNCOMPRESSIBLE_AUDIO_FORMATS
    )

    def supported_formats(self) -> list[str]:
        return audio_compression_formats()

    def preflight_batch(
        self, ui: JobUI, params: Any, proceed: Callable[[], None]
    ) -> None:
        self._preflight_by_support(
            ui, proceed, lambda f: f.suffix.lower() in self._COMPRESSIBLE_EXTS
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
    ) -> FileResult:
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
