import logging
import time
from pathlib import Path
from typing import Dict, Callable, Optional, List

from src.image.compression.file_compressor import file_compressor
from src.utils.progress import ProgressInfo
from src.utils.scanner import scan_image_files

logger = logging.getLogger(__name__)


def directory_compressor(
        input_dir: Path,
        output_dir: Path,
        quality: int = 80,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None
) -> Dict[str, any]:
    stats = {
        "success": 0,
        "failed": 0,
        "elapsed_seconds": 0.0,
        "original_bytes": 0,
        "compressed_bytes": 0,
        "cancelled": False,
        "cleaned_files_count": 0,
    }
    start_time = time.perf_counter()
    created_destination_files: List[Path] = []

    try:
        image_files = scan_image_files(input_dir)
        total_files = len(image_files)

        if total_files == 0:
            logger.warning(f"No valid image files found in '{input_dir}'.")
            return stats

        for index, file_path in enumerate(image_files, start=1):
            relative_path = file_path.relative_to(input_dir)
            destination_path = output_dir / relative_path

            orig_size = file_path.stat().st_size
            stats["original_bytes"] += orig_size

            # Tenta a compressão
            success = file_compressor(
                input_path=file_path,
                output_path=destination_path,
                quality=quality
            )

            comp_size = 0
            if success:
                stats["success"] += 1
                if destination_path.exists():
                    created_destination_files.append(destination_path)
                    comp_size = destination_path.stat().st_size
                    stats["compressed_bytes"] += comp_size
            else:
                stats["failed"] += 1

            # Chama a atualização de progresso (sem destination_path para não quebrar a Dataclass)
            if progress_callback:
                progress_info = ProgressInfo(
                    current=index,
                    total=total_files,
                    start_time=start_time,
                    file_path=file_path,
                    success=success,
                    orig_bytes=orig_size,
                    comp_bytes=comp_size
                )
                # Se a interface solicitar cancelamento dentro da callback, dispara InterruptedError
                progress_callback(progress_info)

        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats

    except InterruptedError:
        logger.info(f"Directory compression cancelled by user: '{input_dir}'")
        stats["cancelled"] = True

        # APAGA TODOS OS ARQUIVOS GERADOS NESTA SESSÃO NO DESTINO
        cleaned_count = 0
        affected_dirs = set()

        for dst_file in created_destination_files:
            if dst_file.exists():
                try:
                    affected_dirs.add(dst_file.parent)
                    dst_file.unlink()
                    cleaned_count += 1
                except Exception as e:
                    logger.warning(f"Failed to remove file {dst_file}: {e}")

        # Limpa pastas vazias criadas no destino
        for folder in affected_dirs:
            try:
                if folder.exists() and not any(folder.iterdir()):
                    folder.rmdir()
            except Exception:
                pass

        stats["cleaned_files_count"] = cleaned_count
        stats["elapsed_seconds"] = round(time.perf_counter() - start_time, 2)
        return stats

    except Exception as e:
        logger.error(f"Failed to compress directory '{input_dir}': {e}", exc_info=True)
        return stats