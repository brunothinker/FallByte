from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.image.image_directory_compression import directory_compressor
from src.image.image_file_compression import file_compressor
from src.utils.output_naming import unique_compression_output_path
from src.utils.progress import ProgressInfo
from ui.controllers.base_controller import BaseController, ProgressCallback
from ui.utils.format_utils import image_compression_formats


@dataclass(frozen=True)
class CompressionOptions:
    """User configuration for an image compression run."""

    quality: int
    strip_metadata: bool = False


class CompressionController(BaseController):
    """Image compression. ``params`` is a ``CompressionOptions``."""

    progress_i18n_key = "msg_compressing_progress"

    def supported_formats(self) -> list[str]:
        return image_compression_formats()

    def build_output_path(
        self, input_path: Path, output_dir: Path, params: CompressionOptions
    ) -> Path:
        return unique_compression_output_path(
            input_path=input_path, output_dir=output_dir
        )

    def run_single_engine(
        self,
        input_path: Path,
        output_path: Path,
        params: CompressionOptions,
        progress_cb: ProgressCallback,
    ) -> bool:
        return file_compressor(
            input_path=input_path,
            output_path=output_path,
            quality=params.quality,
            strip_metadata=params.strip_metadata,
        )

    def run_batch_engine(
        self,
        input_dir: Path,
        output_dir: Path,
        params: CompressionOptions,
        progress_callback: Callable[[ProgressInfo], None],
    ) -> dict[str, Any]:
        return directory_compressor(
            input_dir=input_dir,
            output_dir=output_dir,
            quality=params.quality,
            strip_metadata=params.strip_metadata,
            progress_callback=progress_callback,
            cancel_event=self.cancel_event,
        )
