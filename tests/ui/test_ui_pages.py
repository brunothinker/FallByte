"""Tests for UI pages rendering and picker registration."""

from unittest.mock import MagicMock, patch

import flet as ft


def test_audio_pages_render_and_register_pickers(mock_page):
    """Verifies that all audio pages build without error, register FilePickers, and expose expected options."""
    from ui.pages.audio_compression_page import create_audio_compression_page
    from ui.pages.audio_conversion_page import create_audio_conversion_page
    from ui.pages.audio_extraction_page import create_audio_extraction_page
    from ui.pages.audio_normalization_page import create_audio_normalization_page
    from ui.utils.format_utils import audio_output_formats

    conv_view = create_audio_conversion_page(mock_page, {}, lambda _: None)
    assert isinstance(conv_view, ft.Container), (
        "[ui] create_audio_conversion_page() must return an ft.Container root view."
    )
    assert len(mock_page.overlay) == 3, (
        "[ui] Audio conversion page must register 3 FilePicker controls (file, folder, output) in page.overlay."
    )

    mock_page.overlay.clear()
    comp_view = create_audio_compression_page(mock_page, {}, lambda _: None)
    assert isinstance(comp_view, ft.Container), (
        "[ui] create_audio_compression_page() must return an ft.Container root view."
    )
    assert len(mock_page.overlay) == 3, (
        "[ui] Audio compression page must register 3 FilePicker controls (file, folder, output) in page.overlay."
    )

    mock_page.overlay.clear()
    ext_view = create_audio_extraction_page(mock_page, {}, lambda _: None)
    assert isinstance(ext_view, ft.Container), (
        "[ui] create_audio_extraction_page() must return an ft.Container root view."
    )
    assert len(mock_page.overlay) == 3, (
        "[ui] Audio extraction page must register 3 FilePicker controls (file, folder, output) in page.overlay."
    )
    ext_controls = ext_view.content.content.controls  # type: ignore[union-attr]
    ext_dropdown = next(c for c in ext_controls if isinstance(c, ft.Dropdown))
    assert [o.key for o in (ext_dropdown.options or [])] == audio_output_formats(), (
        "[ui] Audio extraction page dropdown must list all target audio output formats."
    )

    mock_page.overlay.clear()
    norm_view = create_audio_normalization_page(mock_page, {}, lambda _: None)
    assert isinstance(norm_view, ft.Container), (
        "[ui] create_audio_normalization_page() must return an ft.Container root view."
    )
    assert len(mock_page.overlay) == 2, (
        "[ui] Audio normalization page must register 2 folder FilePicker controls (source folder, output) in page.overlay."
    )
    norm_controls = norm_view.content.content.controls  # type: ignore[union-attr]
    norm_dropdown = next(c for c in norm_controls if isinstance(c, ft.Dropdown))
    assert [o.key for o in (norm_dropdown.options or [])] == [
        "music",
        "podcast",
        "broadcast",
    ], (
        "[ui] Audio normalization page dropdown must expose ['music', 'podcast', 'broadcast'] presets."
    )
    assert norm_dropdown.value == "music", (
        "[ui] Audio normalization page dropdown must default to 'music' preset."
    )


def test_image_resize_page_renders_and_register_pickers(mock_page):
    """Verifies that image resize page builds without error, registers FilePickers, and exposes expected modes."""
    from ui.pages.image_resize_page import create_image_resize_page

    resize_view = create_image_resize_page(mock_page, {}, lambda _: None)
    assert isinstance(resize_view, ft.Container), (
        "[ui] create_image_resize_page() must return an ft.Container root view."
    )
    assert len(mock_page.overlay) == 3, (
        "[ui] Image resize page must register 3 FilePicker controls (file, folder, output) in page.overlay."
    )

    resize_controls = resize_view.content.content.controls  # type: ignore[union-attr]
    mode_dropdown = next(c for c in resize_controls if isinstance(c, ft.Dropdown))
    assert [o.key for o in (mode_dropdown.options or [])] == [
        "dimension",
        "percentage",
    ], (
        "[ui] Image resize page dropdown must expose ['dimension', 'percentage'] modes."
    )
    assert mode_dropdown.value == "dimension", (
        "[ui] Image resize page dropdown must default to 'dimension' mode."
    )


def test_image_metadata_page_renders_and_registers_pickers(mock_page):
    """Verifies that image metadata removal page builds without error and registers FilePickers."""
    from ui.pages.image_metadata_page import create_image_metadata_page

    metadata_view = create_image_metadata_page(mock_page, {}, lambda _: None)
    assert isinstance(metadata_view, ft.Container), (
        "[ui] create_image_metadata_page() must return an ft.Container root view."
    )
    assert len(mock_page.overlay) == 3, (
        "[ui] Image metadata page must register 3 FilePicker controls (file, folder, output) in page.overlay."
    )


def test_image_compression_page_renders_strip_metadata_checkbox(mock_page):
    """Verifies image compression page renders unchecked strip_metadata checkbox and forwards its state."""
    from ui.pages.image_compression_page import create_compression_page

    mock_page.overlay.clear()
    comp_view = create_compression_page(mock_page, {}, lambda _: None)
    assert isinstance(comp_view, ft.Container)
    assert len(mock_page.overlay) == 3

    controls = comp_view.content.content.controls  # type: ignore[union-attr]
    chk_strip = next(c for c in controls if isinstance(c, ft.Checkbox))
    assert chk_strip.value is False, (
        "[ui] Image compression strip_metadata checkbox must default to False."
    )

    btn_action = next(c for c in controls if isinstance(c, ft.ElevatedButton))
    chk_strip.value = True

    with patch(
        "ui.pages.image_compression_page.CompressionController.handle_action_click"
    ) as mock_click:
        assert callable(btn_action.on_click)
        btn_action.on_click(MagicMock())
        mock_click.assert_called_once()
        assert mock_click.call_args.kwargs["strip_metadata"] is True
