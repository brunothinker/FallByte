import logging
from pathlib import Path
from src.video.conversion.directory_conversion import directory_converter
from src.video.utils.video_progress import VideoProgressInfo
from ui.controllers.video_conversion_controller import SUPPORTED_VIDEO_CONVERSION_FORMATS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def handle_progress(progress: VideoProgressInfo) -> None:
    """Callback para monitorar o progresso em tempo real."""
    print(
        f"  └─ [{progress.current_file_index}/{progress.total_files}] "
        f"Arquivo: {progress.file_path.name} | "
        f"Sucesso: {progress.success} | "
        f"Tempo: {progress.elapsed_seconds}s"
    )


if __name__ == "__main__":
    INPUT_DIR = Path("/home/bhzinn/Vídeos/Teste")
    OUTPUT_DIR = Path("/home/bhzinn/Downloads/Teste_Conversoes")

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("==================================================")
    print(f"=== INICIANDO SUÍTE DE TESTES: {len(SUPPORTED_VIDEO_CONVERSION_FORMATS)} FORMATOS ===")
    print("==================================================\n")

    summary_report = {}

    for fmt in SUPPORTED_VIDEO_CONVERSION_FORMATS:
        print(f"\n[TESTANDO FORMATO DESTINO: .{fmt.upper()}]")

        results = directory_converter(
            input_dir=INPUT_DIR,
            output_dir=OUTPUT_DIR,
            target_format=fmt,
            progress_callback=handle_progress,
        )

        summary_report[fmt] = {
            "success": results.get("success", 0),
            "failed": results.get("failed", 0),
            "elapsed": results.get("elapsed_seconds", 0),
            "cancelled": results.get("cancelled", False),
        }

    print("\n" + "=" * 50)
    print("=== RELATÓRIO FINAL DE CONVERSÃO ===")
    print("=" * 50)

    for fmt, data in summary_report.items():
        status = "OK" if data["failed"] == 0 and data["success"] > 0 else "FALHA / VAZIO"
        print(
            f"Formato: {fmt.upper():<8} | "
            f"Status: {status:<12} | "
            f"Sucessos: {data['success']} | "
            f"Falhas: {data['failed']} | "
            f"Tempo: {data['elapsed']}s"
        )