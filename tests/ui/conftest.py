"""Shared fixtures and characterization context for UI controller tests (`tests/ui/`)."""

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from ui.controllers.image_resize_controller import ResizeOptions

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
        "id": "image-resize",
        "module": "ui.controllers.image_resize_controller",
        "cls": "ImageResizeController",
        "file_engine": "file_resizer",
        "dir_engine": "directory_resizer",
        "entry": "execute_resize",
        "batch": "_execute_batch_directory",
        "kwargs": {
            "options": ResizeOptions(
                mode="dimension",
                max_width=1280,
                max_height=720,
                percentage=None,
            )
        },
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
    {
        "id": "audio-compression",
        "module": "ui.controllers.audio_compression_controller",
        "cls": "AudioCompressionController",
        "file_engine": "file_compressor",
        "dir_engine": "directory_compressor",
        "entry": "prepare_and_execute",
        "batch": "_run_batch_compression",
        "kwargs": {"quality": 80},
        "has_cancel_event": True,
        "in_name": "track.mp3",
    },
    {
        "id": "audio-conversion",
        "module": "ui.controllers.audio_conversion_controller",
        "cls": "AudioConversionController",
        "file_engine": "file_converter",
        "dir_engine": "directory_converter",
        "entry": "execute_conversion",
        "batch": "_execute_batch_directory",
        "kwargs": {"target_format": "opus"},
        "has_cancel_event": True,
        "in_name": "track.wav",
    },
    {
        "id": "audio-extraction",
        "module": "ui.controllers.audio_extraction_controller",
        "cls": "AudioExtractionController",
        "file_engine": "file_extractor",
        "dir_engine": "directory_extractor",
        "entry": "execute_extraction",
        "batch": "_execute_batch_directory",
        "kwargs": {"target_format": "mp3"},
        "has_cancel_event": True,
        "in_name": "clip.mp4",
    },
    {
        "id": "audio-normalization",
        "module": "ui.controllers.audio_normalization_controller",
        "cls": "AudioNormalizationController",
        "file_engine": None,
        "dir_engine": "directory_normalizer",
        "entry": "execute_normalization",
        "batch": "_execute_batch_directory",
        "kwargs": {"preset_key": "music"},
        "has_cancel_event": True,
        "supports_single": False,
        "in_name": "track.mp3",
    },
    {
        "id": "image-metadata",
        "module": "ui.controllers.image_metadata_controller",
        "cls": "ImageMetadataController",
        "file_engine": "file_metadata_remover",
        "dir_engine": "directory_metadata_remover",
        "entry": "execute_metadata_removal",
        "batch": "_execute_batch_directory",
        "kwargs": {},
        "has_cancel_event": True,
        "in_name": "photo.png",
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
        if not self.spec.get("supports_single", True):
            pytest.skip(f"{self.spec['id']} is directory-only.")
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
        if not self.spec.get("file_engine"):
            return

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
    if spec.get("file_engine"):
        monkeypatch.setattr(
            module, spec["file_engine"], getattr(module, spec["file_engine"])
        )
    monkeypatch.setattr(module, spec["dir_engine"], getattr(module, spec["dir_engine"]))
    return c
