import logging
import threading

import flet as ft

from src.audio.audio_directory_normalization import directory_normalizer
from src.audio.audio_file_normalization import (
    DEFAULT_LOUDNESS_PRESET,
    NORMALIZABLE_AUDIO_FORMATS,
)
from src.utils.progress import ProgressInfo
from ui.components.dialog_utils import (
    show_no_supported_files_dialog,
    show_summary_dialog,
)
from ui.controllers.base_controller import BaseController
from ui.i18n import t
from ui.theme import get_color
from ui.utils.log_capture import TextRedirector

logger = logging.getLogger(__name__)


def normalizable_audio_formats() -> list[str]:
    """Returns sorted uppercase audio format names supported by loudness normalization."""
    return sorted(fmt.upper() for fmt in NORMALIZABLE_AUDIO_FORMATS)


class AudioNormalizationController(BaseController):
    """Controller managing batch directory audio loudness normalization logic."""

    def __init__(self) -> None:
        """Initializes state variables for audio normalization execution and safety guards."""
        super().__init__()
        self.cancel_event: threading.Event = threading.Event()

    def _on_cancel_confirmed(self) -> None:
        """Hook override triggering cancellation event for active normalization processes."""
        self.cancel_event.set()

    def handle_action_click(
        self,
        page: ft.Page,
        preset_key: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Routes trigger button click to execute normalization or request cancellation."""
        if self.is_processing:
            self._confirm_cancel_process(page, lbl_status, progress_bar, btn_action)
        else:
            self.execute_normalization(
                page,
                preset_key,
                lbl_status,
                progress_bar,
                btn_action,
            )

    def execute_normalization(
        self,
        page: ft.Page,
        preset_key: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Validates selected folders and starts background batch loudness normalization."""
        validation_error = self.validate_paths()
        if validation_error or not self.selected_input:
            lbl_status.value = t(validation_error or "msg_select_required")
            lbl_status.color = get_color("error")
            lbl_status.update()
            return

        if not self.selected_input.is_dir():
            lbl_status.value = t("msg_select_required")
            lbl_status.color = get_color("error")
            lbl_status.update()
            return

        threading.Thread(
            target=self._execute_batch_directory,
            args=(
                page,
                preset_key or DEFAULT_LOUDNESS_PRESET,
                lbl_status,
                progress_bar,
                btn_action,
            ),
            daemon=True,
        ).start()

    def _execute_batch_directory(
        self,
        page: ft.Page,
        preset_key: str,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes batch directory loudness normalization with progress tracking."""
        if not self.selected_input or not self.selected_output_dir:
            return

        self._set_processing_ui(page, progress_bar, btn_action)
        self.cancel_event.clear()
        progress_bar.value = 0
        progress_bar.update()

        def update_progress(info: ProgressInfo) -> None:
            if self.abort_requested:
                raise InterruptedError("CANCELLED_BY_USER")

            if info.total > 0:
                progress_bar.value = info.percentage / 100.0
                file_name = info.file_path.name if info.file_path else ""

                if info.is_completed:
                    if info.success:
                        print(f"[OK] {file_name}")
                    else:
                        print(f"[FAIL] {file_name}")

                status_text = t(
                    "msg_normalizing_progress",
                    current=info.current,
                    total=info.total,
                    filename=file_name,
                )
                if info.speed > 0.0:
                    status_text += f" ({info.speed:.1f}x)"

                lbl_status.value = status_text
                progress_bar.update()
                lbl_status.update()

        redirector = TextRedirector()
        redirector.start()

        summary = {}
        try:
            summary = directory_normalizer(
                input_dir=self.selected_input,
                output_dir=self.selected_output_dir,
                preset_key=preset_key,
                progress_callback=update_progress,
                cancel_event=self.cancel_event,
            )

            if summary.get("cancelled", False):
                self.abort_requested = True

            self._close_cancel_dialog(page)

            if not self.abort_requested:
                if summary.get("error"):
                    logger.error(
                        f"Batch normalization returned an error: {summary['error']}"
                    )
                    lbl_status.value = t("msg_error")
                    lbl_status.color = get_color("error")
                    lbl_status.update()
                    return

                if summary.get("no_files", False):
                    lbl_status.value = ""
                    lbl_status.update()
                    self._restore_idle_ui(page, progress_bar, btn_action)
                    show_no_supported_files_dialog(page, normalizable_audio_formats())
                    return

                progress_bar.value = 1.0
                progress_bar.update()

                success_cnt = summary.get("success", 0)
                total_cnt = summary.get("success", 0) + summary.get("failed", 0)

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
            logger.exception("Batch normalization failed unexpectedly")
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
