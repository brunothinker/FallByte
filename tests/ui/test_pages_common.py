"""UI: teste de paginas que cobre varias funcionalidades de uma vez."""

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
