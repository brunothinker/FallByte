"""Testes transversais: isolamento de arquitetura entre pacotes."""

import ast
from pathlib import Path


def test_audio_module_has_zero_cross_imports_from_video_or_image():
    """Enforces domain isolation: `src/audio/` must never import `src.video` or `src.image`."""
    audio_root = Path(__file__).resolve().parents[2] / "src" / "audio"
    py_files = list(audio_root.rglob("*.py"))
    assert py_files, (
        f"[audio] Expected Python modules under '{audio_root}', found none."
    )

    forbidden_prefixes = ("src.video", "src.image")
    violations: list[str] = []

    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden_prefixes):
                        violations.append(f"{py_file.name}: import {alias.name}")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith(forbidden_prefixes)
            ):
                violations.append(f"{py_file.name}: from {node.module} import ...")

    assert not violations, (
        "[audio] Architectural isolation broken: `src/audio/` imported forbidden domain modules: "
        f"{violations}"
    )
