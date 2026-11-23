"""UI: compression/conversion/format/path utils + log_capture."""

import sys


def test_text_redirector_handles_none_standard_streams(monkeypatch):
    """Ensures TextRedirector works without AttributeError when sys.stdout/sys.stderr are None (windowed builds)."""
    from ui.utils.log_capture import TextRedirector

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    redirector = TextRedirector()
    redirector.start()
    try:
        print("[OK] processed sample.mp4")
        sys.stdout.flush()
    finally:
        redirector.stop()

    assert "[OK] processed sample.mp4" in redirector.get_logs(), (
        "[ui] TextRedirector failed to buffer stdout output when underlying sys.stdout was None."
    )
    assert sys.stdout is None, (
        "[ui] TextRedirector.stop() failed to restore original None sys.stdout stream."
    )
    assert sys.stderr is None, (
        "[ui] TextRedirector.stop() failed to restore original None sys.stderr stream."
    )


def test_format_utils_lists_follow_scanners():
    """Format lists shown in the UI must come from the scanners and not drift."""
    from ui.controllers.audio_normalization_controller import (
        normalizable_audio_formats,
    )
    from ui.utils.format_utils import (
        audio_compression_formats,
        audio_input_formats,
        audio_output_formats,
        image_compression_formats,
        image_input_formats,
        video_input_formats,
    )

    assert {"JPG", "PNG", "WEBP", "BMP", "GIF"} <= set(image_input_formats()), (
        "[ui] image_input_formats() must expose all core scanner-supported image extensions."
    )
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
        normalizable_audio_formats()
    ), (
        "[ui] normalizable_audio_formats() must match the exact set of normalizable audio formats."
    )
