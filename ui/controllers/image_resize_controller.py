import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import flet as ft

from src.image.image_directory_resize import directory_resizer
from src.image.image_file_resize import UNRESIZABLE_FORMATS, file_resizer
from ui.components.dialog_utils import (
    show_no_supported_files_dialog,
    show_summary_dialog,
)
from ui.controllers.base_controller import BaseController
from ui.i18n import t
from ui.theme import get_color
from ui.utils.format_utils import image_input_formats
from ui.utils.log_capture import TextRedirector

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResizeOptions:
    """Validated user configuration for an image resize execution."""

    mode: str
    max_width: int | None
    max_height: int | None
    percentage: int | None


def unique_resize_output_path(input_path: Path, output_dir: Path) -> Path:
    """Computes a collision-free output file path for single-file image resizing."""
    ext = input_path.suffix.lower().lstrip(".")
    if ext.upper() in UNRESIZABLE_FORMATS:
        ext = "png"

    stem = input_path.stem
    candidate = output_dir / (f"{stem}_resized.{ext}" if ext else f"{stem}_resized")
    index = 2
    while candidate.exists():
        candidate = (
            output_dir / f"{stem}_resized_{index}.{ext}"
            if ext
            else output_dir / f"{stem}_resized_{index}"
        )
        index += 1
    return candidate


class ImageResizeController(BaseController):
    """Controller managing single-file and batch directory image resizing logic."""

    def __init__(self) -> None:
        """Initializes state variables for image resize execution and safety guards."""
        super().__init__()
        self.cancel_event: threading.Event = threading.Event()

    def _on_cancel_confirmed(self) -> None:
        """Hook override triggering cancellation event for active resize processes."""
        self.cancel_event.set()

    def handle_action_click(
        self,
        page: ft.Page,
        options: ResizeOptions,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Routes trigger button click to execute resize or request cancellation."""
        if self.is_processing:
            self._confirm_cancel_process(page, lbl_status, progress_bar, btn_action)
        else:
            self.execute_resize(
                page=page,
                options=options,
                lbl_status=lbl_status,
                progress_bar=progress_bar,
                btn_action=btn_action,
            )

    def execute_resize(
        self,
        page: ft.Page,
        options: ResizeOptions,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Validates paths and resize parameters before starting background execution."""
        validation_error = self.validate_paths()
        if validation_error or not self.selected_input:
            lbl_status.value = t(validation_error or "msg_select_required")
            lbl_status.color = get_color("error")
            lbl_status.update()
            return

        if options.mode == "dimension" and not (
            (options.max_width and options.max_width > 0)
            or (options.max_height and options.max_height > 0)
        ):
            lbl_status.value = t("msg_invalid_resize_dimensions")
            lbl_status.color = get_color("error")
            lbl_status.update()
            return

        if options.mode == "percentage" and (
            options.percentage is None or not (1 <= options.percentage <= 100)
        ):
            lbl_status.value = t("msg_invalid_resize_percentage")
            lbl_status.color = get_color("error")
            lbl_status.update()
            return

        self.cancel_event.clear()

        if self.selected_input.is_file():
            threading.Thread(
                target=self._execute_single_file,
                args=(page, options, lbl_status, progress_bar, btn_action),
                daemon=True,
            ).start()
        else:
            threading.Thread(
                target=self._execute_batch_directory,
                args=(page, options, lbl_status, progress_bar, btn_action),
                daemon=True,
            ).start()

    def _execute_single_file(
        self,
        page: ft.Page,
        options: ResizeOptions,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes single-file image resizing flow and presents summary dialog."""
        if not self.selected_input or not self.selected_output_dir:
            return

        self._set_processing_ui(page, progress_bar, btn_action)

        out_file = unique_resize_output_path(
            input_path=self.selected_input,
            output_dir=self.selected_output_dir,
        )
        pre_existed = out_file.exists()

        lbl_status.value = t(
            "msg_resizing_progress",
            current=1,
            total=1,
            filename=self.selected_input.name,
        )
        lbl_status.color = get_color("text")
        lbl_status.update()

        redirector = TextRedirector()
        redirector.start()

        start_time = time.time()
        orig_bytes = self.selected_input.stat().st_size
        success = False

        try:
            success = file_resizer(
                input_path=self.selected_input,
                output_path=out_file,
                mode=options.mode,
                max_width=options.max_width,
                max_height=options.max_height,
                percentage=options.percentage,
            )
            if success:
                print(f"[OK] {self.selected_input.name}")
            else:
                print(f"[FAIL] {self.selected_input.name}")
        except Exception as err:
            success = False
            print(f"[ERROR] {self.selected_input.name}: {err}")
        finally:
            redirector.stop()

        elapsed = time.time() - start_time
        comp_bytes = out_file.stat().st_size if success and out_file.exists() else 0

        self._close_cancel_dialog(page)

        if not self.abort_requested:
            if success:
                lbl_status.value = t("msg_success")
                lbl_status.color = get_color("success")
            else:
                lbl_status.value = t("msg_error")
                lbl_status.color = get_color("error")
            lbl_status.update()

            summary = {
                "total_files": 1,
                "success": 1 if success else 0,
                "failed": 0 if success else 1,
                "elapsed_seconds": round(elapsed, 2),
                "original_bytes": orig_bytes,
                "compressed_bytes": comp_bytes,
                "terminal_log": redirector.get_logs(),
                "errors": []
                if success
                else [{"file": self.selected_input.name, "error": t("msg_error")}],
            }
            show_summary_dialog(page, summary)
        else:
            if not pre_existed and out_file.exists():
                try:
                    out_file.unlink()
                except OSError:
                    pass
            lbl_status.value = t("msg_process_cancelled", count=1)
            lbl_status.color = get_color("error")
            lbl_status.update()

        self._restore_idle_ui(page, progress_bar, btn_action)

    def _execute_batch_directory(
        self,
        page: ft.Page,
        options: ResizeOptions,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes batch directory image resizing with progress tracking."""
        if not self.selected_input or not self.selected_output_dir:
            return

        self._set_processing_ui(page, progress_bar, btn_action)
        progress_bar.value = 0
        progress_bar.update()

        def update_progress(info) -> None:
            if self.abort_requested or self.cancel_event.is_set():
                raise InterruptedError("CANCELLED_BY_USER")

            if info.total > 0:
                progress_bar.value = info.current / info.total
                filename = info.file_path.name if info.file_path else ""

                if info.is_completed:
                    if info.success:
                        print(f"[OK] {filename}")
                    else:
                        print(f"[FAIL] {filename}")

                lbl_status.value = t(
                    "msg_resizing_progress",
                    current=info.current,
                    total=info.total,
                    filename=filename,
                )
                progress_bar.update()
                lbl_status.update()

        redirector = TextRedirector()
        redirector.start()

        summary = {}
        try:
            summary = directory_resizer(
                input_dir=self.selected_input,
                output_dir=self.selected_output_dir,
                mode=options.mode,
                max_width=options.max_width,
                max_height=options.max_height,
                percentage=options.percentage,
                progress_callback=update_progress,
                cancel_event=self.cancel_event,
            )

            if summary.get("cancelled", False):
                self.abort_requested = True

            self._close_cancel_dialog(page)

            if not self.abort_requested:
                if summary.get("error"):
                    logger.error(
                        f"Batch resize returned an error: {summary['error']}"
                    )
                    lbl_status.value = t("msg_error")
                    lbl_status.color = get_color("error")
                    lbl_status.update()
                    return

                if summary.get("no_files", False):
                    lbl_status.value = ""
                    lbl_status.update()
                    self._restore_idle_ui(page, progress_bar, btn_action)
                    show_no_supported_files_dialog(page, image_input_formats())
                    return

                progress_bar.value = 1.0
                progress_bar.update()

                success_cnt = summary.get("success", summary.get("successful", 0))
                total_cnt = summary.get("total_files", summary.get("total", 0))

                lbl_status.value = t(
                    "msg_success_summary",
                    msg=t("msg_success"),
                    successful=success_cnt,
                    total=total_cnt,
                )
                lbl_status.color = get_color("success")
                lbl_status.update()

                summary["terminal_log"] = redirector.get_logs()
                show_summary_dialog(page, summary)

        except InterruptedError as err:
            self.abort_requested = True
            print(f"[FAIL] {err}")

        except Exception as err:
            logger.exception("Batch resize failed unexpectedly")
            print(f"[ERROR] {err}")
            lbl_status.value = t("msg_error")
            lbl_status.color = get_color("error")
            lbl_status.update()

        finally:
            redirector.stop()
            self._close_cancel_dialog(page)

            if self.abort_requested:
                cleaned_count = summary.get("cleaned_files_count", 0)
                lbl_status.value = t("msg_process_cancelled", count=cleaned_count)
                lbl_status.color = get_color("error")
                lbl_status.update()

            self._restore_idle_ui(page, progress_bar, btn_action)
