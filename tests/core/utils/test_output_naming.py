"""Core: output_naming + output_directory."""

from concurrent.futures import ThreadPoolExecutor

from src.utils.output_directory import create_unique_output_dir


def test_create_unique_output_dir_uses_base_name_first(tmp_path):
    """Uses the plain folder name when it is still free."""
    result = create_unique_output_dir(tmp_path, "compressed")

    assert result == tmp_path / "compressed", (
        "[batch] Expected create_unique_output_dir() to use the unsuffixed base name when free."
    )
    assert result.is_dir(), (
        "[batch] create_unique_output_dir() must materialize the session directory on disk."
    )


def test_create_unique_output_dir_uses_first_available_suffix(tmp_path):
    """Picks the first free numeric suffix and leaves existing folders untouched."""
    for name in ("compressed", "compressed_1", "compressed_3"):
        (tmp_path / name).mkdir()

    result = create_unique_output_dir(tmp_path, "compressed")

    assert result == tmp_path / "compressed_2", (
        "[batch] Expected create_unique_output_dir() to pick the lowest available numeric suffix ('compressed_2')."
    )
    assert result.is_dir(), (
        "[batch] Newly allocated suffixed session directory must exist on disk."
    )
    assert (tmp_path / "compressed").is_dir(), (
        "[batch] Existing base session directory must remain intact."
    )
    assert (tmp_path / "compressed_1").is_dir(), (
        "[batch] Existing 'compressed_1' directory must remain intact."
    )
    assert (tmp_path / "compressed_3").is_dir(), (
        "[batch] Existing 'compressed_3' directory must remain intact."
    )


def test_create_unique_output_dir_creates_missing_parent(tmp_path):
    """Creates the missing parent directories together with the session folder."""
    parent = tmp_path / "nested" / "destination"

    result = create_unique_output_dir(parent, "converted")

    assert result == parent / "converted", (
        "[batch] Expected create_unique_output_dir() to return the nested session path."
    )
    assert result.is_dir(), (
        "[batch] create_unique_output_dir() must recursively create missing parent directories."
    )


def test_create_unique_output_dir_is_safe_for_concurrent_calls(tmp_path):
    """Guarantees distinct folders when called from several threads at once."""

    def create_folder(_):
        return create_unique_output_dir(tmp_path, "converted")

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create_folder, range(8)))

    assert len(set(results)) == 8, (
        "[batch] Concurrent calls to create_unique_output_dir() collided instead of returning 8 distinct directories."
    )
    assert all(path.is_dir() for path in results), (
        "[batch] Every directory returned by concurrent create_unique_output_dir() calls must exist."
    )
    assert {path.name for path in results} == {
        "converted",
        *(f"converted_{index}" for index in range(1, 8)),
    }, (
        "[batch] Concurrent session folder allocation did not produce the expected sequential suffix set."
    )
