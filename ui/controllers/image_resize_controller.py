from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.image.image_directory_resize import directory_resizer
from src.image.image_file_resize import UNRESIZABLE_FORMATS, file_resizer
from src.utils.output_naming import unique_resize_output_path
from src.utils.progress import ProgressInfo
from ui.controllers.base_controller import BaseController, ProgressCallback
from ui.utils.format_utils import image_input_formats


@dataclass(frozen=True)
class ResizeOptions:
    """Validated user configuration for an image resize execution."""

    mode: str
    max_width: int | None
    max_height: int | None
    percentage: int | None


class ImageResizeController(BaseController):
    """Image resize. ``params`` is a ``ResizeOptions``."""

    progress_i18n_key = "msg_resizing_progress"

    def supported_formats(self) -> list[str]:
        return image_input_formats()

    def validate_params(self, params: ResizeOptions) -> str | None:
        if params.mode == "dimension" and not (
            (params.max_width and params.max_width > 0)
            or (params.max_height and params.max_height > 0)
        ):
            return "msg_invalid_resize_dimensions"

        if params.mode == "percentage" and (
            params.percentage is None or not (1 <= params.percentage <= 100)
        ):
            return "msg_invalid_resize_percentage"

        return None

    def build_output_path(
        self, input_path: Path, output_dir: Path, params: ResizeOptions
    ) -> Path:
        ext = input_path.suffix.lstrip(".").upper()
        return unique_resize_output_path(
            input_path=input_path,
            output_dir=output_dir,
            target_format="png" if ext in UNRESIZABLE_FORMATS else None,
        )

    def run_single_engine(
        self,
        input_path: Path,
        output_path: Path,
        params: ResizeOptions,
        progress_cb: ProgressCallback,
    ) -> bool:
        return file_resizer(
            input_path=input_path,
            output_path=output_path,
            mode=params.mode,
            max_width=params.max_width,
            max_height=params.max_height,
            percentage=params.percentage,
        )

    def run_batch_engine(
        self,
        input_dir: Path,
        output_dir: Path,
        params: ResizeOptions,
        progress_callback: Callable[[ProgressInfo], None],
    ) -> dict[str, Any]:
        return directory_resizer(
            input_dir=input_dir,
            output_dir=output_dir,
            mode=params.mode,
            max_width=params.max_width,
            max_height=params.max_height,
            percentage=params.percentage,
            progress_callback=progress_callback,
            cancel_event=self.cancel_event,
        )
