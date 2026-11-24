from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.image.image_directory_conversion import directory_converter
from src.image.image_file_conversion import file_converter
from src.utils.file_result import FileResult
from src.utils.output_naming import unique_conversion_output_path
from src.utils.progress import ProgressInfo
from ui.controllers.base_controller import BaseController, ProgressCallback
from ui.utils.conversion_utils import resolve_color_key_to_hex
from ui.utils.format_utils import image_input_formats


@dataclass(frozen=True)
class ConversionOptions:
    """Validated user configuration for an image conversion execution."""

    target_format: str
    color_key: str = "color_white"


class ConversionController(BaseController):
    """Image conversion. ``params`` is a ``ConversionOptions``."""

    progress_i18n_key = "msg_converting_progress"

    def supported_formats(self) -> list[str]:
        return image_input_formats()

    def build_output_path(
        self, input_path: Path, output_dir: Path, params: ConversionOptions
    ) -> Path:
        return unique_conversion_output_path(
            input_path=input_path,
            output_dir=output_dir,
            target_format=params.target_format.lower(),
        )

    def run_single_engine(
        self,
        input_path: Path,
        output_path: Path,
        params: ConversionOptions,
        progress_cb: ProgressCallback,
    ) -> FileResult:
        return file_converter(
            input_path=input_path,
            output_path=output_path,
            target_format=params.target_format.lower(),
            transparency_replacement_color=resolve_color_key_to_hex(params.color_key),
        )

    def run_batch_engine(
        self,
        input_dir: Path,
        output_dir: Path,
        params: ConversionOptions,
        progress_callback: Callable[[ProgressInfo], None],
    ) -> dict[str, Any]:
        return directory_converter(
            input_dir=input_dir,
            output_dir=output_dir,
            target_format=params.target_format.lower(),
            transparency_replacement_color=resolve_color_key_to_hex(params.color_key),
            progress_callback=progress_callback,
            cancel_event=self.cancel_event,
        )
