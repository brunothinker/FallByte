"""Guarda: tests/core nao pode sombrear o pacote real `src`."""

from pathlib import Path

import src.formats


def test_src_formats_is_loaded_from_real_src_package():
    """`import src.formats` must resolve to <repo>/src, never to tests/core."""
    repo_root = Path(__file__).resolve().parents[2]
    loaded = Path(src.formats.__file__).resolve()
    assert loaded == repo_root / "src" / "formats.py", (
        f"[tests] `src.formats` was loaded from {loaded}, expected {repo_root / 'src' / 'formats.py'}."
    )
