"""Tests for UI theme resolution, format lists, reusable cards, module registry, and pages."""

from unittest.mock import MagicMock

import flet as ft


def test_theme_get_color_danger_resolution():
    """Verifies get_color returns static danger color without fallback to white."""
    from ui.theme import get_color

    danger_color = get_color("danger")
    assert danger_color == ft.colors.RED_600, (
        "[ui] get_color('danger') must resolve to static ft.colors.RED_600."
    )
    assert danger_color != "#FFFFFF", (
        "[ui] get_color('danger') must not fall back to default white '#FFFFFF'."
    )


def test_format_utils_lists_follow_scanners():
    """Format lists shown in the UI must come from the scanners and not drift."""
    from ui.utils.format_utils import (
        audio_compression_formats,
        audio_input_formats,
        audio_normalization_formats,
        audio_output_formats,
        image_compression_formats,
        image_input_formats,
        video_input_formats,
    )

    assert {"JPG", "PNG", "WEBP", "BMP", "GIF"} <= set(image_input_formats()), (
        "[ui] image_input_formats() must expose all core scanner-supported image extensions."
    )
    # Scanned-but-uncompressible formats are not advertised for compression.
    assert not {"BMP", "PPM", "GIF", "ICO"} & set(image_compression_formats()), (
        "[ui] Uncompressible image formats (BMP, PPM, GIF, ICO) must be excluded from compression options."
    )
    assert {"JPG", "PNG", "WEBP"} <= set(image_compression_formats()), (
        "[ui] image_compression_formats() must include compressible formats (JPG, PNG, WEBP)."
    )
    assert {"MP4", "MKV", "WEBM", "MOV", "AVI", "WMV", "FLV", "M4V"} <= set(
        video_input_formats()
    ), (
        "[ui] video_input_formats() must expose all scanner-supported video container extensions."
    )

    # Audio input, target output, lossy-only compression, and normalization formats
    assert {"MP3", "M4A", "AAC", "OGG", "OPUS", "FLAC", "WAV", "WMA", "AIFF"} <= set(
        audio_input_formats()
    ), "[ui] audio_input_formats() must expose all scanner-supported audio extensions."
    assert {"MP3", "M4A", "OPUS", "OGG", "FLAC", "WAV"} == set(
        audio_output_formats()
    ), (
        "[ui] audio_output_formats() must match the exact set of supported target conversion formats."
    )
    assert not {"FLAC", "WAV", "WMA", "AIFF"} & set(audio_compression_formats()), (
        "[ui] Lossless/uncompressible audio formats (FLAC, WAV, WMA, AIFF) must be excluded from compression formats."
    )
    assert {"MP3", "M4A", "AAC", "OGG", "OPUS"} == set(audio_compression_formats()), (
        "[ui] audio_compression_formats() must include only lossy compressible audio formats."
    )
    assert {"MP3", "M4A", "AAC", "OGG", "OPUS", "FLAC", "WAV"} == set(
        audio_normalization_formats()
    ), (
        "[ui] audio_normalization_formats() must match the exact set of normalizable audio formats."
    )


def test_create_path_label_defaults_and_custom_text():
    """Validates create_path_label initialization with default i18n text and custom strings."""
    from ui.components.path_label import create_path_label

    lbl_default = create_path_label()
    assert isinstance(lbl_default, ft.Text), (
        "[ui] create_path_label() must return an ft.Text control."
    )
    assert lbl_default.size == 11, (
        "[ui] Path label font size must default to 11px for compact card layout."
    )
    assert lbl_default.max_lines == 1, (
        "[ui] Path label must restrict text to a single line (max_lines=1) to prevent card overflow."
    )
    assert lbl_default.overflow == ft.TextOverflow.ELLIPSIS, (
        "[ui] Path label must truncate long paths with TextOverflow.ELLIPSIS."
    )

    lbl_custom = create_path_label("custom/path/file.png")
    assert lbl_custom.value == "custom/path/file.png", (
        "[ui] create_path_label() must display the caller-provided custom path string."
    )


def test_create_source_picker_card_structure_and_callbacks():
    """Verifies that create_source_picker_card renders PopupMenuButton and triggers selection callbacks."""
    from ui.components.path_label import create_path_label
    from ui.components.source_picker_card import create_source_picker_card

    file_callback_called = False
    folder_callback_called = False

    def on_file():
        nonlocal file_callback_called
        file_callback_called = True

    def on_folder():
        nonlocal folder_callback_called
        folder_callback_called = True

    lbl_in_path = create_path_label()
    card = create_source_picker_card(
        lbl_in_path=lbl_in_path,
        on_select_file=on_file,
        on_select_folder=on_folder,
        file_icon=ft.icons.VIDEO_FILE,
    )

    assert isinstance(card, ft.Container), (
        "[ui] create_source_picker_card() must wrap the picker trigger in an ft.Container."
    )
    assert isinstance(card.content, ft.PopupMenuButton), (
        "[ui] Source picker card content must be an ft.PopupMenuButton offering file/folder choice."
    )

    popup_menu = card.content
    assert popup_menu.items is not None, (
        "[ui] Source picker PopupMenuButton must define selectable menu items."
    )
    assert len(popup_menu.items) == 2, (
        "[ui] Source picker PopupMenuButton must expose exactly 2 items (file and folder)."
    )

    item_file = popup_menu.items[0]
    item_folder = popup_menu.items[1]

    assert isinstance(item_file, ft.PopupMenuItem), (
        "[ui] First source picker menu entry must be an ft.PopupMenuItem for file selection."
    )
    assert isinstance(item_folder, ft.PopupMenuItem), (
        "[ui] Second source picker menu entry must be an ft.PopupMenuItem for folder selection."
    )
    assert item_file.icon == ft.icons.VIDEO_FILE, (
        "[ui] File menu item must use the custom file_icon passed to create_source_picker_card()."
    )
    assert item_folder.icon == ft.icons.FOLDER, (
        "[ui] Folder menu item must display the standard ft.icons.FOLDER icon."
    )

    if callable(item_file.on_click):
        item_file.on_click(MagicMock())
    assert file_callback_called is True, (
        "[ui] Clicking the file PopupMenuItem must invoke on_select_file callback."
    )

    if callable(item_folder.on_click):
        item_folder.on_click(MagicMock())
    assert folder_callback_called is True, (
        "[ui] Clicking the folder PopupMenuItem must invoke on_select_folder callback."
    )


def test_module_registry_route_and_active_state_resolution():
    """Verifies route resolution and active module matching using module IDs."""
    from ui.registry import get_all_routes, resolve_active_module_id

    routes = get_all_routes()
    assert "home" in routes, "[ui] Module registry must register the 'home' route."
    assert "image_hub" in routes, (
        "[ui] Module registry must register the 'image_hub' route."
    )
    assert "video_hub" in routes, (
        "[ui] Module registry must register the 'video_hub' route."
    )
    assert "audio_hub" in routes, (
        "[ui] Module registry must register the 'audio_hub' route."
    )
    assert "image_conversion" in routes, (
        "[ui] Module registry must register the 'image_conversion' route."
    )
    assert "image_resize" in routes, (
        "[ui] Module registry must register the 'image_resize' route."
    )
    assert "video_compression" in routes, (
        "[ui] Module registry must register the 'video_compression' route."
    )
    assert "audio_conversion" in routes, (
        "[ui] Module registry must register the 'audio_conversion' route."
    )
    assert "audio_compression" in routes, (
        "[ui] Module registry must register the 'audio_compression' route."
    )
    assert "audio_extraction" in routes, (
        "[ui] Module registry must register the 'audio_extraction' route."
    )
    assert "audio_normalization" in routes, (
        "[ui] Module registry must register the 'audio_normalization' route."
    )

    # Active module ID resolution without string splitting
    assert resolve_active_module_id("home") == "home", (
        "[ui] resolve_active_module_id('home') must map to 'home'."
    )
    assert resolve_active_module_id("image_hub") == "image", (
        "[ui] resolve_active_module_id('image_hub') must map to 'image'."
    )
    assert resolve_active_module_id("image_conversion") == "image", (
        "[ui] resolve_active_module_id('image_conversion') must map to 'image'."
    )
    assert resolve_active_module_id("image_resize") == "image", (
        "[ui] resolve_active_module_id('image_resize') must map to 'image'."
    )
    assert resolve_active_module_id("video_compression") == "video", (
        "[ui] resolve_active_module_id('video_compression') must map to 'video'."
    )
    assert resolve_active_module_id("audio_hub") == "audio", (
        "[ui] resolve_active_module_id('audio_hub') must map to 'audio'."
    )
    assert resolve_active_module_id("audio_conversion") == "audio", (
        "[ui] resolve_active_module_id('audio_conversion') must map to 'audio'."
    )
    assert resolve_active_module_id("audio_compression") == "audio", (
        "[ui] resolve_active_module_id('audio_compression') must map to 'audio'."
    )
    assert resolve_active_module_id("audio_extraction") == "audio", (
        "[ui] resolve_active_module_id('audio_extraction') must map to 'audio'."
    )
    assert resolve_active_module_id("audio_normalization") == "audio", (
        "[ui] resolve_active_module_id('audio_normalization') must map to 'audio'."
    )
    assert resolve_active_module_id("unknown_route") == "", (
        "[ui] Unrecognized routes must resolve to an empty active module ID ''."
    )


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


def test_image_resize_page_renders_and_registers_pickers(mock_page):
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
