from pathlib import Path


def create_unique_output_dir(output_dir: Path, folder_name: str) -> Path:
    index = 0

    while True:
        suffix = f"_{index}" if index else ""
        candidate = output_dir / f"{folder_name}{suffix}"

        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            index += 1