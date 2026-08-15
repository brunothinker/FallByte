import logging
from pathlib import Path
from src.video.compression.directory_compression import directory_compressor
from src.video.utils.video_progress import VideoProgressInfo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def handle_progress(progress: VideoProgressInfo) -> None:
    """Callback para monitorar o progresso da compressão em tempo real."""
    orig_mb = progress.orig_bytes / (1024 * 1024) if progress.orig_bytes else 0
    comp_mb = progress.comp_bytes / (1024 * 1024) if progress.comp_bytes else 0
    print(
        f"  └─ [{progress.current_file_index}/{progress.total_files}] "
        f"Arquivo: {progress.file_path.name} | "
        f"Sucesso: {progress.success} | "
        f"Orig: {orig_mb:.2f}MB -> Comp: {comp_mb:.2f}MB | "
        f"Economia: {progress.space_saved_percentage:.1f}%"
    )


if __name__ == "__main__":
    INPUT_DIR = Path("/home/bhzinn/Downloads/Teste_Conversoes")
    BASE_OUTPUT_DIR = Path("/home/bhzinn/Vídeos/Teste_Compressed")

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    TEST_QUALITIES = [30, 60, 90]

    print("==================================================")
    print("=== INICIANDO SUÍTE DE TESTES DE COMPRESSÃO ===")
    print("==================================================\n")

    summary_report = {}

    for q in TEST_QUALITIES:
        out_dir = BASE_OUTPUT_DIR / f"Qualidade_{q}"
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[TESTANDO COMPRESSÃO COM QUALIDADE: {q}%]")

        results = directory_compressor(
            input_dir=INPUT_DIR,
            output_dir=out_dir,
            quality=q,
            progress_callback=handle_progress,
        )

        summary_report[f"Qualidade_{q}"] = {
            "success": results.get("success", 0),
            "failed": results.get("failed", 0),
            "elapsed": results.get("elapsed_seconds", 0),
            "orig_bytes": results.get("original_bytes", 0),
            "comp_bytes": results.get("compressed_bytes", 0),
        }

    print("\n" + "=" * 50)
    print("=== RELATÓRIO FINAL DE COMPRESSÃO ===")
    print("=" * 50)

    for key, data in summary_report.items():
        orig_mb = data["orig_bytes"] / (1024 * 1024)
        comp_mb = data["comp_bytes"] / (1024 * 1024)
        savings = (
            ((orig_mb - comp_mb) / orig_mb) * 100 if orig_mb > 0 else 0
        )
        print(
            f"{key:<14} | "
            f"Sucessos: {data['success']} | "
            f"Falhas: {data['failed']} | "
            f"Tamanho: {orig_mb:.2f}MB -> {comp_mb:.2f}MB (-{savings:.1f}%)"
        )