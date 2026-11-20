import logging
import threading
import time
from pathlib import Path

import flet as ft

from src.utils.output_naming import unique_conversion_output_path
from src.video.utils.video_ffmpeg_utils import MediaTrack
from src.video.video_track_selector import (
    inspect_video_tracks,
    remux_selected_tracks,
)
from ui.components.dialog_utils import show_summary_dialog
from ui.controllers.base_controller import BaseController
from ui.i18n import t
from ui.theme import get_color
from ui.utils.log_capture import TextRedirector

logger = logging.getLogger(__name__)

__all__ = ["VideoTracksController"]


class VideoTracksController(BaseController):
    """Controller managing single-file video track inspection and lossless remuxing."""

    def __init__(self) -> None:
        """Initializes state variables for track selection and execution."""
        super().__init__()
        self.cancel_event: threading.Event = threading.Event()
        self.audio_tracks: list[MediaTrack] = []
        self.subtitle_tracks: list[MediaTrack] = []
        self._track_checkboxes: dict[int, ft.Checkbox] = {}

    def _on_cancel_confirmed(self) -> None:
        """Hook override triggering cancellation event for active remuxing processes."""
        self.cancel_event.set()

    def handle_video_selected(
        self,
        e: ft.FilePickerResultEvent,
        lbl_in_path: ft.Text,
        lbl_status: ft.Text,
        tracks_container: ft.Column,
        audio_list_col: ft.Column,
        subtitle_list_col: ft.Column,
    ) -> None:
        """Handles single video file selection, inspects embedded streams, and updates checklists."""
        self.handle_input_result(e, lbl_in_path, lbl_status)

        if not self.selected_input or not self.selected_input.is_file():
            self.audio_tracks = []
            self.subtitle_tracks = []
            self._track_checkboxes.clear()
            tracks_container.visible = False
            tracks_container.update()
            return

        lbl_status.value = t("msg_inspecting_tracks")
        lbl_status.color = get_color("subtext")
        lbl_status.update()

        audio_tracks, subtitle_tracks = inspect_video_tracks(self.selected_input)
        self.audio_tracks = audio_tracks
        self.subtitle_tracks = subtitle_tracks
        self._track_checkboxes.clear()

        self._populate_track_group(
            target_col=audio_list_col,
            tracks=audio_tracks,
            empty_key="msg_no_audio_tracks",
        )
        self._populate_track_group(
            target_col=subtitle_list_col,
            tracks=subtitle_tracks,
            empty_key="msg_no_subtitle_tracks",
        )

        tracks_container.visible = True
        tracks_container.update()

        lbl_status.value = ""
        lbl_status.update()

    def _populate_track_group(
        self,
        target_col: ft.Column,
        tracks: list[MediaTrack],
        empty_key: str,
    ) -> None:
        """Rebuilds checkbox controls for a given track group or shows an empty placeholder."""
        target_col.controls.clear()

        if not tracks:
            target_col.controls.append(
                ft.Text(
                    t(empty_key),
                    size=12,
                    italic=True,
                    color=get_color("subtext"),
                )
            )
            return

        for track in tracks:
            cb = ft.Checkbox(
                label=track.display_label(),
                value=True,
                active_color=get_color("primary"),
            )
            self._track_checkboxes[track.stream_index] = cb
            target_col.controls.append(cb)

    def get_selected_stream_indices(self) -> list[int]:
        """Returns sorted stream indices for all currently checked audio and subtitle tracks."""
        return sorted(
            stream_idx
            for stream_idx, cb in self._track_checkboxes.items()
            if cb.value
        )

    def handle_action_click(
        self,
        page: ft.Page,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Routes trigger button click to execute remuxing or request cancellation."""
        if self.is_processing:
            self._confirm_cancel_process(page, lbl_status, progress_bar, btn_action)
        else:
            self.execute_remux(page, lbl_status, progress_bar, btn_action)

    def execute_remux(
        self,
        page: ft.Page,
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Validates single-file input and launches background lossless remuxing."""
        validation_error = self.validate_paths()
        if validation_error or not self.selected_input:
            lbl_status.value = t(validation_error or "msg_select_required")
            lbl_status.color = get_color("error")
            lbl_status.update()
            return

        if not self.selected_input.is_file():
            lbl_status.value = t("msg_single_video_required")
            lbl_status.color = get_color("error")
            lbl_status.update()
            return

        selected_indices = self.get_selected_stream_indices()

        threading.Thread(
            target=self._execute_single_file,
            args=(
                page,
                selected_indices,
                lbl_status,
                progress_bar,
                btn_action,
            ),
            daemon=True,
        ).start()

    def _build_output_path(self, input_path: Path, output_dir: Path) -> Path:
        """Generates a non-colliding output path preserving the original container extension."""
        original_ext = input_path.suffix.lstrip(".").lower() or "mkv"
        return unique_conversion_output_path(
            input_path=input_path,
            output_dir=output_dir,
            target_format=original_ext,
        )

    def _execute_single_file(
        self,
        page: ft.Page,
        selected_indices: list[int],
        lbl_status: ft.Text,
        progress_bar: ft.ProgressBar,
        btn_action: ft.ElevatedButton,
    ) -> None:
        """Executes single-file lossless track remuxing and presents summary dialog."""
        if not self.selected_input or not self.selected_output_dir:
            return

        filename = self.selected_input.name
        self._set_processing_ui(page, progress_bar, btn_action)
        self.cancel_event.clear()

        out_file = self._build_output_path(
            self.selected_input, self.selected_output_dir
        )

        lbl_status.value = t("msg_remuxing_progress", filename=filename)
        lbl_status.color = get_color("text")
        lbl_status.update()

        redirector = TextRedirector()
        redirector.start()

        start_time = time.time()
        orig_bytes = self.selected_input.stat().st_size
        success = False

        def file_progress_cb(processed: float, fps: float, speed: float) -> None:
            if self.abort_requested:
                return
            status_text = t("msg_remuxing_progress", filename=filename)
            if speed > 0.0:
                status_text += f" ({speed:.1f}x)"
            lbl_status.value = status_text
            lbl_status.update()

        try:
            success = remux_selected_tracks(
                input_path=self.selected_input,
                output_path=out_file,
                selected_stream_indices=selected_indices,
                cancel_event=self.cancel_event,
                progress_callback=file_progress_cb,
            )
            if success:
                progress_bar.value = 1.0
                progress_bar.update()
                print(f"[OK] {filename} -> {out_file.name}")
            else:
                print(f"[FAIL] {filename}")
        except InterruptedError:
            self.abort_requested = True
            print(f"[CANCELLED] {filename}")
        except Exception as err:
            success = False
            print(f"[ERROR] {filename}: {err}")
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
                else [{"file": filename, "error": t("msg_error")}],
            }
            show_summary_dialog(page, summary)
        else:
            if out_file.exists():
                try:
                    out_file.unlink()
                except OSError:
                    pass
            lbl_status.value = t("msg_process_cancelled", count=1)
            lbl_status.color = get_color("error")
            lbl_status.update()

        self._restore_idle_ui(page, progress_bar, btn_action)
