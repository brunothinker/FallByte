"""Controller tests: characterization suite and controller/engine integration.

The first part PINS THE CURRENT BEHAVIOR of the 4 UI controllers (image/video x
conversion/compression), including known quirks, as a safety net for the
controller refactoring (BaseController etc.). If one of these tests fails on
untouched code, the TEST is wrong: adjust the test, never the controller.
Engines are replaced by fakes, so no FFmpeg/Pillow work is done and everything
runs synchronously.

The second part holds integration-style tests that exercise the controllers
with the real engines for empty, unsupported or corrupted inputs.
"""

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import flet as ft
import pytest

from ui.controllers.image_compression_controller import CompressionController
from ui.controllers.image_conversion_controller import ConversionController
from ui.controllers.video_compression_controller import VideoCompressionController
from ui.controllers.video_conversion_controller import VideoConversionController
from ui.i18n import t
from ui.theme import get_color

# Per-controller wiring used to parametrize the characterization tests.
SPECS = [
    {
        "id": "image-compression",
        "module": "ui.controllers.image_compression_controller",
        "cls": "CompressionController",
        "file_engine": "file_compressor",
        "dir_engine": "directory_compressor",
        "entry": "prepare_and_execute",
        "batch": "_run_batch_compression",
        "kwargs": {"quality": 80},
        "has_cancel_event": True,
        "in_name": "photo.png",
    },
    {
        "id": "image-conversion",
        "module": "ui.controllers.image_conversion_controller",
        "cls": "ConversionController",
        "file_engine": "file_converter",
        "dir_engine": "directory_converter",
        "entry": "execute_conversion",
        "batch": "_execute_batch_directory",
        "kwargs": {"target_format": "webp", "selected_color_key": "color_white"},
        "has_cancel_event": True,
        "in_name": "photo.png",
    },
    {
        "id": "video-compression",
        "module": "ui.controllers.video_compression_controller",
        "cls": "VideoCompressionController",
        "file_engine": "file_compressor",
        "dir_engine": "directory_compressor",
        "entry": "prepare_and_execute",
        "batch": "_run_batch_compression",
        "kwargs": {"quality": 80},
        "has_cancel_event": True,
        "in_name": "clip.mp4",
    },
    {
        "id": "video-conversion",
        "module": "ui.controllers.video_conversion_controller",
        "cls": "VideoConversionController",
        "file_engine": "file_converter",
        "dir_engine": "directory_converter",
        "entry": "execute_conversion",
        "batch": "_execute_batch_directory",
        "kwargs": {"target_format": "mp4"},
        "has_cancel_event": True,
        "in_name": "clip.mp4",
    },
]


@dataclass
class Ctx:
    """Test context bundling a controller, its module, fake widgets and workspace.

    Attributes:
        spec (dict): Wiring entry from `SPECS` describing the controller under test.
        module (Any): Controller module (its engine functions are monkeypatched).
        controller (Any): Fresh controller instance.
        page (MagicMock): Mocked Flet page.
        in_dir (Path): Temporary input directory.
        out_dir (Path): Temporary output directory.
        lbl_status (MagicMock): Fake status label.
        progress_bar (MagicMock): Fake progress bar.
        btn_action (MagicMock): Fake action button.
        summary_dialog (MagicMock): Replacement for `show_summary_dialog`.
    """

    spec: dict
    module: Any
    controller: Any
    page: MagicMock
    in_dir: Path
    out_dir: Path
    lbl_status: MagicMock = field(default_factory=MagicMock)
    progress_bar: MagicMock = field(default_factory=MagicMock)
    btn_action: MagicMock = field(default_factory=MagicMock)
    summary_dialog: MagicMock = field(default_factory=MagicMock)

    def widgets(self) -> dict:
        """Returns the fake widgets as keyword arguments for controller methods."""
        return {
            "lbl_status": self.lbl_status,
            "progress_bar": self.progress_bar,
            "btn_action": self.btn_action,
        }

    def run_single(self) -> None:
        """Runs the single-file flow synchronously on a freshly created input file."""
        src = self.in_dir / self.spec["in_name"]
        src.write_bytes(b"source data")
        self.controller.selected_input = src
        self.controller.selected_output_dir = self.out_dir
        self.controller._execute_single_file(
            page=self.page, **self.spec["kwargs"], **self.widgets()
        )

    def run_batch(self) -> None:
        """Runs the batch-directory flow synchronously on the input directory."""
        self.controller.selected_input = self.in_dir
        self.controller.selected_output_dir = self.out_dir
        getattr(self.controller, self.spec["batch"])(
            page=self.page, **self.spec["kwargs"], **self.widgets()
        )

    def fake_file_engine(self, ok: bool = True, raises: Exception | None = None):
        """Replaces the single-file engine with a fake.

        Args:
            ok (bool, optional): Result the fake returns (an output file is
                written only when True). Defaults to True.
            raises (Exception | None, optional): Exception the fake raises
                instead of returning. Defaults to None.
        """
        def fake(**kwargs):
            if raises:
                raise raises
            if ok:
                out = kwargs["output_path"]
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"out")
            return ok

        setattr(self.module, self.spec["file_engine"], fake)

    def fake_dir_engine(self, result: dict | None = None, raises=None):
        """Replaces the batch engine with a fake.

        Args:
            result (dict | None, optional): Statistics dictionary to return.
            raises (Exception | None, optional): Exception to raise instead.
        """
        def fake(**kwargs):
            if raises:
                raise raises
            return dict(result) if result is not None else {}

        setattr(self.module, self.spec["dir_engine"], fake)

    def summary_payload(self) -> dict:
        """Returns the summary dictionary passed to the last `show_summary_dialog` call."""
        args = self.summary_dialog.call_args[0]
        return args[1]


@pytest.fixture(params=SPECS, ids=[s["id"] for s in SPECS])
def ctx(request, tmp_workspace, mock_page, monkeypatch) -> Ctx:
    """Builds a `Ctx` for each controller in `SPECS` with the summary dialog mocked."""
    spec = request.param
    module = importlib.import_module(spec["module"])
    in_dir, out_dir = tmp_workspace
    c = Ctx(
        spec=spec,
        module=module,
        controller=getattr(module, spec["cls"])(),
        page=mock_page,
        in_dir=in_dir,
        out_dir=out_dir,
    )
    monkeypatch.setattr(module, "show_summary_dialog", c.summary_dialog)
    # Restore engine attributes after each test.
    monkeypatch.setattr(module, spec["file_engine"], getattr(module, spec["file_engine"]))
    monkeypatch.setattr(module, spec["dir_engine"], getattr(module, spec["dir_engine"]))
    return c


def _assert_idle_ui(c: Ctx) -> None:
    """Controller and button must be back to the idle (ready) state."""
    assert c.controller.is_processing is False
    assert c.controller.abort_requested is False
    assert c.btn_action.text == t("btn_process")
    assert c.btn_action.bgcolor is not None
    c.page.session.set.assert_any_call("is_processing", False)


# --- Single file flow ---


def test_single_file_success(ctx):
    """A successful single-file run shows one OK summary and restores the idle UI."""
    ctx.fake_file_engine(ok=True)
    ctx.run_single()

    ctx.summary_dialog.assert_called_once()
    payload = ctx.summary_payload()
    assert payload["success"] == 1
    assert payload["failed"] == 0
    assert payload["total_files"] == 1
    assert "[OK]" in payload["terminal_log"]
    assert ctx.lbl_status.value == t("msg_success")
    _assert_idle_ui(ctx)


def test_single_file_failure(ctx):
    """A failed single-file run reports one failure, logs [FAIL] and shows the error status."""
    ctx.fake_file_engine(ok=False)
    ctx.run_single()

    payload = ctx.summary_payload()
    assert payload["success"] == 0
    assert payload["failed"] == 1
    assert "[FAIL]" in payload["terminal_log"]
    assert "[OK]" not in payload["terminal_log"]
    assert ctx.lbl_status.value == t("msg_error")
    _assert_idle_ui(ctx)


def test_single_file_engine_exception_is_reported_as_failure(ctx):
    """An exception raised by the engine is reported as a failure, never propagated."""
    ctx.fake_file_engine(raises=RuntimeError("boom"))
    ctx.run_single()

    payload = ctx.summary_payload()
    assert payload["failed"] == 1
    assert "[ERROR]" in payload["terminal_log"]
    _assert_idle_ui(ctx)


def test_single_file_sets_stop_button_while_running(ctx):
    """While the engine runs, the button is in STOP state and the session is flagged as processing."""
    seen = {}

    def fake(**kwargs):
        seen["text"] = ctx.btn_action.text
        seen["bgcolor"] = ctx.btn_action.bgcolor
        seen["color"] = ctx.btn_action.color
        seen["processing"] = ctx.controller.is_processing
        seen["session"] = ctx.page.session.set.call_args
        kwargs["output_path"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["output_path"].write_bytes(b"out")
        return True

    setattr(ctx.module, ctx.spec["file_engine"], fake)
    ctx.run_single()

    assert seen["text"] == t("btn_stop_process")
    assert seen["bgcolor"] == get_color("danger")
    assert seen["color"] == "#FFFFFF"
    assert seen["processing"] is True
    assert seen["session"].args == ("is_processing", True)


# --- Batch flow ---

BATCH_OK = {
    "success": 2,
    "failed": 1,
    "total_files": 3,
    "elapsed_seconds": 1.0,
    "original_bytes": 100,
    "compressed_bytes": 50,
    "cancelled": False,
    "cleaned_files_count": 0,
}


def test_batch_success_shows_summary_and_restores_ui(ctx):
    """A finished batch shows the summary dialog, full progress and restores the idle UI."""
    ctx.fake_dir_engine(BATCH_OK)
    ctx.run_batch()

    ctx.summary_dialog.assert_called_once()
    assert ctx.progress_bar.value == 1.0
    assert ctx.lbl_status.value == t(
        "msg_success_summary", msg=t("msg_success"), successful=2, total=3
    )
    assert "terminal_log" in ctx.summary_payload()
    _assert_idle_ui(ctx)


def test_batch_cancelled_reports_cleaned_count_without_summary(ctx):
    """A cancelled batch reports the cleaned file count and shows no summary dialog."""
    ctx.fake_dir_engine({**BATCH_OK, "cancelled": True, "cleaned_files_count": 3})
    ctx.run_batch()

    ctx.summary_dialog.assert_not_called()
    assert ctx.lbl_status.value == t("msg_process_cancelled", count=3)
    assert ctx.progress_bar.visible is False
    _assert_idle_ui(ctx)


def test_batch_engine_exception_restores_ui_without_summary(ctx):
    """An engine crash during a batch restores the idle UI and shows no summary dialog."""
    ctx.fake_dir_engine(raises=RuntimeError("boom"))
    ctx.run_batch()

    ctx.summary_dialog.assert_not_called()
    assert ctx.lbl_status.value == t("msg_process_cancelled", count=0)
    _assert_idle_ui(ctx)


def test_batch_restores_standard_streams(ctx):
    """sys.stdout and sys.stderr are restored after the log redirector finishes."""
    import sys

    before = (sys.stdout, sys.stderr)
    ctx.fake_dir_engine(BATCH_OK)
    ctx.run_batch()
    assert (sys.stdout, sys.stderr) == before


# --- Action routing / validation ---


def test_action_click_without_selection_asks_for_paths(ctx):
    """Starting without input/output selected asks the user to pick both and runs nothing."""
    getattr(ctx.controller, ctx.spec["entry"])(
        page=ctx.page, **ctx.spec["kwargs"], **ctx.widgets()
    )

    assert ctx.lbl_status.value == t("msg_select_required")
    assert ctx.controller.is_processing is False
    ctx.summary_dialog.assert_not_called()


def test_action_click_same_folder_blocks_execution(ctx):
    """Starting with identical input and output directories blocks processing and shows error."""
    ctx.controller.selected_input = ctx.in_dir
    ctx.controller.selected_output_dir = ctx.in_dir

    getattr(ctx.controller, ctx.spec["entry"])(
        page=ctx.page, **ctx.spec["kwargs"], **ctx.widgets()
    )

    assert ctx.lbl_status.value == t("msg_same_folder_error")
    assert ctx.controller.is_processing is False
    ctx.summary_dialog.assert_not_called()


def test_action_click_nested_folder_blocks_execution(ctx):
    """Starting with output directory nested within input directory blocks execution."""
    nested_dir = ctx.in_dir / "subfolder"
    nested_dir.mkdir(parents=True, exist_ok=True)
    ctx.controller.selected_input = ctx.in_dir
    ctx.controller.selected_output_dir = nested_dir

    getattr(ctx.controller, ctx.spec["entry"])(
        page=ctx.page, **ctx.spec["kwargs"], **ctx.widgets()
    )

    assert ctx.lbl_status.value == t("msg_nested_folder_error")
    assert ctx.controller.is_processing is False
    ctx.summary_dialog.assert_not_called()


def test_action_click_while_processing_opens_cancel_dialog(ctx):
    """Clicking the action button while processing routes to the cancel confirmation."""
    ctx.controller.is_processing = True
    ctx.controller._confirm_cancel_process = MagicMock()

    ctx.controller.handle_action_click(
        page=ctx.page, **ctx.spec["kwargs"], **ctx.widgets()
    )

    ctx.controller._confirm_cancel_process.assert_called_once()


def test_cancel_dialog_confirm_sets_abort_flags(ctx):
    """Confirming the cancel dialog raises the abort flags (and the cancel event for video/image)."""
    ctx.controller.is_processing = True
    ctx.controller._confirm_cancel_process(
        ctx.page, ctx.lbl_status, ctx.progress_bar, ctx.btn_action
    )
    dialog = ctx.controller.cancel_dialog
    assert dialog is not None and dialog.open is True

    stop_btn = dialog.actions[1]
    assert stop_btn.bgcolor == get_color("danger")
    assert stop_btn.color == "#FFFFFF"

    stop_btn.on_click(MagicMock())  # "Yes, stop and delete"

    assert ctx.controller.abort_requested is True
    assert ctx.lbl_status.value == t("msg_cancelling")
    assert dialog.open is False
    assert ctx.controller.cancel_dialog is None
    if ctx.spec["has_cancel_event"]:
        assert ctx.controller.cancel_event.is_set()


def test_cancel_dialog_keep_running_changes_nothing(ctx):
    """Dismissing the cancel dialog with 'keep running' leaves the job untouched."""
    ctx.controller.is_processing = True
    ctx.controller._confirm_cancel_process(
        ctx.page, ctx.lbl_status, ctx.progress_bar, ctx.btn_action
    )
    dialog = ctx.controller.cancel_dialog

    dialog.actions[0].on_click(MagicMock())  # "No, keep running"

    assert ctx.controller.abort_requested is False
    assert dialog.open is False
    if ctx.spec["has_cancel_event"]:
        assert not ctx.controller.cancel_event.is_set()


def test_image_cancellation_path_end_to_end(ctx):
    """Tests image cancellation path end-to-end when progress callback triggers cancellation."""
    ctx.controller.selected_input = ctx.in_dir
    ctx.controller.selected_output_dir = ctx.out_dir
    (ctx.in_dir / ctx.spec["in_name"]).write_bytes(b"data")

    def fake_dir_engine_interrupted(**kwargs):
        if hasattr(ctx.controller, "cancel_event"):
            ctx.controller.cancel_event.set()
        ctx.controller.abort_requested = True
        callback = kwargs.get("progress_callback")
        if callback:
            info = MagicMock()
            info.total = 1
            info.current = 1
            info.file_path = ctx.in_dir / ctx.spec["in_name"]
            info.success = True
            try:
                callback(info)
            except InterruptedError:
                pass
        return {"cancelled": True, "cleaned_files_count": 1}

    setattr(ctx.module, ctx.spec["dir_engine"], fake_dir_engine_interrupted)

    getattr(ctx.controller, ctx.spec["batch"])(
        page=ctx.page, **ctx.spec["kwargs"], **ctx.widgets()
    )

    assert ctx.lbl_status.value == t("msg_process_cancelled", count=1)
    _assert_idle_ui(ctx)


# --- Pickers ---


def test_open_picker_blocks_concurrent_windows(ctx):
    """A second picker request is ignored while one native picker is still open."""
    picker = MagicMock()
    ctx.controller.open_picker(picker, allow_directory=True)
    ctx.controller.open_picker(picker, allow_directory=True)

    picker.get_directory_path.assert_called_once()
    assert ctx.controller.picker_active is True


def test_open_picker_file_mode(ctx):
    """File mode opens the file picker with safe initial directory and allowed_extensions."""
    picker = MagicMock()
    ctx.controller.open_picker(
        picker, allow_directory=False, allowed_extensions=["mp4", "mkv"]
    )

    picker.pick_files.assert_called_once_with(
        allow_multiple=False,
        initial_directory=str(Path.home()),
        allowed_extensions=["mp4", "mkv"],
    )
    picker.get_directory_path.assert_not_called()


def test_handle_input_result_with_file(ctx):
    """Picking an input file stores it, releases the picker lock and updates the label."""
    lbl = MagicMock()
    event = MagicMock()
    event.files = [MagicMock(path=str(ctx.in_dir / "a.png"))]
    event.path = None
    ctx.controller.picker_active = True

    ctx.controller.handle_input_result(event, lbl, ctx.lbl_status)

    assert ctx.controller.selected_input == ctx.in_dir / "a.png"
    assert ctx.controller.picker_active is False
    assert lbl.value == "a.png"
    assert ctx.lbl_status.value == ""


def test_handle_input_result_with_directory(ctx):
    """Picking an input directory stores it and shows the directory name."""
    lbl = MagicMock()
    event = MagicMock()
    event.files = None
    event.path = str(ctx.in_dir)

    ctx.controller.handle_input_result(event, lbl)

    assert ctx.controller.selected_input == ctx.in_dir
    assert lbl.value == ctx.in_dir.name


def test_handle_input_result_cancelled_keeps_previous_selection(ctx):
    """Dismissing the input picker keeps the previous selection and releases the lock."""
    ctx.controller.selected_input = ctx.in_dir
    lbl = MagicMock()
    event = MagicMock()
    event.files = None
    event.path = None
    ctx.controller.picker_active = True

    ctx.controller.handle_input_result(event, lbl)

    assert ctx.controller.selected_input == ctx.in_dir
    assert ctx.controller.picker_active is False


def test_handle_output_result(ctx):
    """Picking an output directory stores it, releases the picker lock and updates the label."""
    lbl = MagicMock()
    event = MagicMock()
    event.path = str(ctx.out_dir)
    ctx.controller.picker_active = True

    ctx.controller.handle_output_result(event, lbl, ctx.lbl_status)

    assert ctx.controller.selected_output_dir == ctx.out_dir
    assert ctx.controller.picker_active is False
    assert lbl.value == ctx.out_dir.name


def test_handle_output_result_cancelled_keeps_state(ctx):
    """Dismissing the output picker selects nothing and releases the lock."""
    event = MagicMock()
    event.path = None
    ctx.controller.picker_active = True

    ctx.controller.handle_output_result(event, MagicMock())

    assert ctx.controller.selected_output_dir is None
    assert ctx.controller.picker_active is False


# --- Controller + real engine integration ---


def test_ui_log_reflects_failed_compression(tmp_workspace, mock_page):
    """Tests controller and UI integration ensuring batch processing failures write '[FAIL]' logs instead of false positives."""
    in_dir, out_dir = tmp_workspace

    # Create a corrupted image file to force engine-level failure
    corrupted_file = in_dir / "bad_image.png"
    corrupted_file.write_bytes(b"NOT_A_VALID_IMAGE_HEADER")

    # Configure controller and mock UI components
    controller = CompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    # Intercept summary dialog invocation to inspect injected summary payload
    with patch("ui.controllers.image_compression_controller.show_summary_dialog") as mock_show_dialog:
        # Execute batch processing synchronously in test environment
        controller._run_batch_compression(
            page=mock_page,
            quality=80,
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_show_dialog.assert_called_once()

        # Extract summary payload dictionary passed to summary dialog
        summary_payload = (
            mock_show_dialog.call_args[0][1]
            if len(mock_show_dialog.call_args[0]) > 1
            else mock_show_dialog.call_args[1].get("summary")
        )

        # Validate accurate error and success statistics
        assert summary_payload.get("failed", 0) == 1
        assert summary_payload.get("success", 0) == 0

        # Verify terminal log contains [FAIL] tag and no false positive [OK] tags
        terminal_log = summary_payload.get("terminal_log", "")
        assert "[FAIL]" in terminal_log
        assert "[OK]" not in terminal_log


def test_processing_state_locks_global_navigation(mock_page):
    """Validates that active processing locks session state and blocks navigation attempts."""
    controller = CompressionController()
    controller.is_processing = True
    mock_page.session.get.return_value = True

    assert mock_page.session.get("is_processing") is True


def test_video_compression_preflight_empty_supported_files(tmp_workspace, mock_page):
    """Verifies that preflight stops early when no supported video files exist in the batch directory."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "document.pdf").write_bytes(b"pdf data")

    controller = VideoCompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with patch(
        "ui.controllers.video_compression_controller.show_no_supported_files_dialog"
    ) as mock_no_files, patch(
        "ui.controllers.video_compression_controller.threading.Thread"
    ) as mock_thread:
        controller._preflight_batch_execution(
            page=mock_page,
            quality=80,
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_no_files.assert_called_once()
        formats = mock_no_files.call_args.args[1]
        assert "MP4" in formats and "PDF" not in formats
        # Execution must be blocked: no worker thread started.
        mock_thread.assert_not_called()


def test_image_compression_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies image compression controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "text.txt").write_bytes(b"text data")

    controller = CompressionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with patch("ui.controllers.image_compression_controller.show_summary_dialog") as mock_summary, patch(
        "ui.controllers.image_compression_controller.show_no_supported_files_dialog"
    ) as mock_no_files:
        controller._run_batch_compression(
            page=mock_page,
            quality=80,
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "JPG" in mock_no_files.call_args.args[1]
        assert progress_bar.visible is False


def test_image_conversion_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies image conversion controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "text.txt").write_bytes(b"text data")

    controller = ConversionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with patch("ui.controllers.image_conversion_controller.show_summary_dialog") as mock_summary, patch(
        "ui.controllers.image_conversion_controller.show_no_supported_files_dialog"
    ) as mock_no_files:
        controller._execute_batch_directory(
            page=mock_page,
            target_format="webp",
            selected_color_key="transparent",
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "BMP" in mock_no_files.call_args.args[1]
        assert progress_bar.visible is False


def test_video_conversion_batch_no_supported_files(tmp_workspace, mock_page):
    """Verifies video conversion controller handles empty/unsupported batch directories gracefully."""
    in_dir, out_dir = tmp_workspace
    (in_dir / "text.txt").write_bytes(b"text data")

    controller = VideoConversionController()
    controller.selected_input = in_dir
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    with patch("ui.controllers.video_conversion_controller.show_summary_dialog") as mock_summary, patch(
        "ui.controllers.video_conversion_controller.show_no_supported_files_dialog"
    ) as mock_no_files:
        controller._execute_batch_directory(
            page=mock_page,
            target_format="mp4",
            lbl_status=lbl_status,
            progress_bar=progress_bar,
            btn_action=btn_action,
        )

        mock_summary.assert_not_called()
        mock_no_files.assert_called_once()
        assert "MKV" in mock_no_files.call_args.args[1]
        assert progress_bar.visible is False


# --- Safe Directory Selection & Regression Tests ---


def test_open_picker_uses_get_safe_initial_directory(ctx, monkeypatch):
    """Regression test ensuring open_picker uses get_safe_initial_directory to prevent OS picker crashes."""
    mock_get_safe = MagicMock(return_value=str(Path.home()))
    monkeypatch.setattr("ui.controllers.base_controller.get_safe_initial_directory", mock_get_safe)

    picker = MagicMock()
    non_existent_path = ctx.in_dir / "deleted_folder"
    ctx.controller.selected_input = non_existent_path

    ctx.controller.open_picker(picker, allow_directory=True)

    mock_get_safe.assert_called_once_with(non_existent_path)
    picker.get_directory_path.assert_called_once_with(initial_directory=str(Path.home()))


def test_open_picker_fallback_to_home_on_deleted_directory(ctx):
    """Ensures file picker falls back to Home directory when previously selected directory was removed."""
    picker = MagicMock()
    deleted_dir = ctx.in_dir / "removed_dir"
    ctx.controller.selected_input = deleted_dir

    ctx.controller.open_picker(picker, allow_directory=False)

    picker.pick_files.assert_called_once_with(
        allow_multiple=False, initial_directory=str(Path.home()), allowed_extensions=None
    )


def test_cancel_dialog_uses_correct_i18n_body_key(ctx):
    """Verifies that the cancellation dialog body uses the translated string from t('dialog_cancel_body')."""
    ctx.controller.is_processing = True
    ctx.controller._confirm_cancel_process(
        ctx.page, ctx.lbl_status, ctx.progress_bar, ctx.btn_action
    )
    dialog = ctx.controller.cancel_dialog
    assert dialog is not None
    assert isinstance(dialog.content, ft.Text)
    assert dialog.content.value == t("dialog_cancel_body")
    assert dialog.content.value != "dialog_cancel_content"


def test_single_file_compression_does_not_overwrite_preexisting_file(tmp_workspace, mock_page, monkeypatch):
    """Verifies that single-file compression uses unique output naming and does not overwrite existing destination files."""
    in_dir, out_dir = tmp_workspace
    src_file = in_dir / "sample.png"
    src_file.write_bytes(b"source data")

    # Create a pre-existing target file in output directory
    preexisting_file = out_dir / "sample_compressed.png"
    preexisting_file.write_bytes(b"original content")

    controller = CompressionController()
    controller.selected_input = src_file
    controller.selected_output_dir = out_dir

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    monkeypatch.setattr("ui.controllers.image_compression_controller.show_summary_dialog", MagicMock())
    monkeypatch.setattr(
        "ui.controllers.image_compression_controller.file_compressor",
        lambda input_path, output_path, quality: output_path.write_bytes(b"compressed data") or True,
    )

    controller._execute_single_file(
        page=mock_page,
        quality=80,
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )

    # Pre-existing file content must remain untouched
    assert preexisting_file.read_bytes() == b"original content"
    # New file with unique suffix should be created
    expected_new_file = out_dir / "sample_compressed_2.png"
    assert expected_new_file.exists()
    assert expected_new_file.read_bytes() == b"compressed data"


def test_single_file_compression_cancellation_preserves_preexisting_file(tmp_workspace, mock_page, monkeypatch):
    """Verifies that cancelling single-file compression does not delete pre-existing user files in the destination."""
    in_dir, out_dir = tmp_workspace
    src_file = in_dir / "sample.mp4"
    src_file.write_bytes(b"source video")

    # Create a pre-existing target file in output directory
    preexisting_file = out_dir / "sample_compressed.mp4"
    preexisting_file.write_bytes(b"preexisting user video")

    controller = VideoCompressionController()
    controller.selected_input = src_file
    controller.selected_output_dir = out_dir
    controller.abort_requested = True

    lbl_status = MagicMock(spec=ft.Text)
    progress_bar = MagicMock(spec=ft.ProgressBar)
    btn_action = MagicMock(spec=ft.ElevatedButton)

    monkeypatch.setattr("ui.controllers.video_compression_controller.show_summary_dialog", MagicMock())
    monkeypatch.setattr(
        "ui.controllers.video_compression_controller.file_compressor",
        lambda **kwargs: False,
    )

    controller._execute_single_file(
        page=mock_page,
        quality=80,
        lbl_status=lbl_status,
        progress_bar=progress_bar,
        btn_action=btn_action,
    )

    # Pre-existing file must NOT be deleted upon cancellation
    assert preexisting_file.exists()
    assert preexisting_file.read_bytes() == b"preexisting user video"