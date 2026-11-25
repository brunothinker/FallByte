"""UI (video): downscale tests (controller and feature page)."""

from unittest.mock import patch

import flet as ft

from src.utils.file_result import FileResult
from tests.ui.helpers import make_job_ui
from ui.controllers.video_downscale_controller import VideoDownscaleController
from ui.i18n import t


def test_video_downscale_single_file_skipped_no_upscale(
    tmp_workspace, mock_page, monkeypatch
):
    """Verifies VideoDownscaleController reports skipped state when video is already <= target resolution."""
    in_dir, out_dir = tmp_workspace
    src_video = in_dir / "hd_clip.mp4"
    src_video.write_bytes(b"source hd video")

    controller = VideoDownscaleController()
    controller.selected_input = src_video
    controller.selected_output_dir = out_dir

    ui = make_job_ui(mock_page)

    def fake_downscaler(
        input_path,
        output_path,
        resolution,
        cancel_event=None,
        file_progress_callback=None,
    ):
        output_path.write_bytes(b"source hd video")
        return FileResult.skipped(
            "skip_no_upscale",
            target_height=1080,
            src_width=1280,
            src_height=720,
        )

    monkeypatch.setattr(
        "ui.controllers.video_downscale_controller.file_downscaler",
        fake_downscaler,
    )

    with patch("ui.controllers.base_controller.show_summary_dialog") as mock_summary:
        controller._run_single_file_job(ui, "1080p")

        mock_summary.assert_called_once()
        payload = mock_summary.call_args[0][1]
        assert payload["success"] == 0
        assert payload["skipped"] == 1
        assert payload["failed"] == 0
        assert "[SKIP]" in payload["terminal_log"]
        assert ui.lbl_status.value == t("msg_kept_original")


def test_video_downscale_page_renders_and_registers_pickers(mock_page):
    """Verifies that video downscale page builds without error, registers FilePickers, and exposes resolution presets."""
    from ui.pages.video_downscale_page import create_video_downscale_page

    downscale_view = create_video_downscale_page(mock_page, {}, lambda _: None)
    assert isinstance(downscale_view, ft.Container), (
        "[ui] create_video_downscale_page() must return an ft.Container root view."
    )
    assert len(mock_page.overlay) == 0, (
        "[ui] Video downscale page must not pollute page.overlay in Flet 0.8+."
    )

    controls = downscale_view.content.content.controls  # type: ignore[union-attr]
    res_dropdown = next(c for c in controls if isinstance(c, ft.Dropdown))
    assert [o.key for o in (res_dropdown.options or [])] == [
        "1080p",
        "720p",
        "480p",
    ], "[ui] Video downscale page dropdown must expose ['1080p', '720p', '480p'] presets."
    assert res_dropdown.value == "1080p", (
        "[ui] Video downscale page dropdown must default to '1080p'."
    )
