from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.image.image_directory_metadata import directory_metadata_remover
from src.image.image_file_metadata import (
    UNWRITABLE_METADATA_FORMATS,
    file_metadata_remover,
)
from src.utils.file_result import FileResult
from src.utils.output_naming import unique_metadata_output_path
from src.utils.progress import ProgressInfo
from ui.controllers.base_controller import BaseController, ProgressCallback
from ui.utils.format_utils import image_input_formats


class ImageMetadataController(BaseController):
    """Image metadata removal. Takes no parameters."""

    progress_i18n_key = "msg_removing_metadata_progress"

    def supported_formats(self) -> list[str]:
        return image_input_formats()

    def build_output_path(self, input_path: Path, output_dir: Path, params: Any) -> Path:
        ext = input_path.suffix.lstrip(".").upper()
        return unique_metadata_output_path(
            input_path=input_path,
            output_dir=output_dir,
            target_format="png" if ext in UNWRITABLE_METADATA_FORMATS else None,
        )

    def run_single_engine(
        self,
        input_path: Path,
        output_path: Path,
        params: Any,
        progress_cb: ProgressCallback,
    ) -> FileResult:
        return file_metadata_remover(input_path=input_path, output_path=output_path)

    def run_batch_engine(
        self,
        input_dir: Path,
        output_dir: Path,
        params: Any,
        progress_callback: Callable[[ProgressInfo], None],
    ) -> dict[str, Any]:
        return directory_metadata_remover(
            input_dir=input_dir,
            output_dir=output_dir,
            progress_callback=progress_callback,
            cancel_event=self.cancel_event,
        )
