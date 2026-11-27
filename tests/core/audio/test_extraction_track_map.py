"""Unit tests for custom audio stream mapping and decoupled track inspection."""

import ast
from pathlib import Path

from src.audio.audio_file_extraction import _build_strategies, file_extractor
from src.audio.utils.audio_ffmpeg_utils import AudioStreamInfo
from src.utils.media_tracks import MediaTrack


def test_build_strategies_default_uses_safe_audio_map():
    strategies = _build_strategies(
        ffmpeg_bin=Path("ffmpeg"),
        input_path=Path("movie.mkv"),
        tmp_path=Path("out.mp3"),
        target_fmt="mp3",
    )
    assert len(strategies) == 2
    for _, cmd in strategies:
        map_idx = cmd.index("-map")
        assert cmd[map_idx + 1] == "0:a:0"
        assert "-vn" in cmd
        assert "-sn" in cmd
        assert "-dn" in cmd


def test_build_strategies_custom_stream_index():
    strategies = _build_strategies(
        ffmpeg_bin=Path("ffmpeg"),
        input_path=Path("dual_audio.mkv"),
        tmp_path=Path("out.mp3"),
        target_fmt="mp3",
        stream_index=2,
    )
    assert len(strategies) == 2
    for _, cmd in strategies:
        map_idx = cmd.index("-map")
        assert cmd[map_idx + 1] == "0:2"
        assert "-vn" in cmd
        assert "-sn" in cmd
        assert "-dn" in cmd


def test_file_extractor_forwards_custom_stream_index(tmp_path, monkeypatch):
    src_video = tmp_path / "sample.mkv"
    src_video.write_bytes(b"fake-video-content")
    out_audio = tmp_path / "extracted.mp3"

    captured_cmds: list[list[str]] = []

    def fake_probe(_ffmpeg_bin, _input_path):
        return AudioStreamInfo(audio_codecs=["aac", "ac3"], duration_seconds=10.0)

    def fake_run(strategies, tmp_out, _name, _cancel, progress_callback=None):
        captured_cmds.extend(cmd for _, cmd in strategies)
        tmp_out.write_bytes(b"fake-mp3-data")
        return strategies[0][0]

    monkeypatch.setattr("src.audio.audio_file_extraction.get_ffmpeg_path", lambda: Path("ffmpeg"))
    monkeypatch.setattr("src.audio.audio_file_extraction.probe_audio_streams", fake_probe)
    monkeypatch.setattr("src.audio.audio_file_extraction.run_audio_strategies", fake_run)

    res = file_extractor(
        input_path=src_video,
        output_path=out_audio,
        target_format="mp3",
        stream_index=3,
    )

    assert res.is_processed
    assert out_audio.exists()
    assert captured_cmds
    for cmd in captured_cmds:
        map_idx = cmd.index("-map")
        assert cmd[map_idx + 1] == "0:3"


def test_src_audio_never_imports_src_video():
    audio_dir = Path("src/audio")
    for py_file in audio_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("src.video"), (
                        f"{py_file} imports {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("src.video"), (
                    f"{py_file} imports from {node.module}"
                )


def test_media_track_display_label():
    track = MediaTrack(
        stream_index=2,
        track_type="audio",
        codec="aac",
        language="por",
        title="Dublado",
        details="stereo",
        is_default=True,
    )
    assert track.display_label() == 'POR — "Dublado" — [AAC, stereo, Default]'
