import logging
from pathlib import Path
from src.video.conversion.directory_conversion import directory_converter
from src.video.utils.video_progress import VideoProgressInfo

# Configura o log para exibir os detalhes no console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


def handle_progress(progress: VideoProgressInfo) -> None:
    """Função de callback para monitorar o progresso em tempo real."""
    print(
        f"[{progress.current_file_index}/{progress.total_files}] "
        f"Arquivo: {progress.file_path.name} | "
        f"Sucesso: {progress.success} | "
        f"Tempo Decorrido: {progress.elapsed_seconds}s"
    )


if __name__ == "__main__":
    # Defina aqui os caminhos para o seu teste local
    INPUT_DIR = Path("/home/bhzinn/Vídeos/Teste")
    OUTPUT_DIR = Path("/home/bhzinn/Downloads/Teste")
    TARGET_FORMAT = "mkv"  # Altere para o formato desejado (mkv, avi, webm, etc.)

    print("=== Iniciando Teste de Conversão de Diretório ===")

    # Cria pasta de teste se não existir para evitar erros manuais
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Executa o conversor de diretório
    results = directory_converter(
        input_dir=INPUT_DIR,
        output_dir=OUTPUT_DIR,
        target_format=TARGET_FORMAT,
        progress_callback=handle_progress
    )

    print("\n=== Resultado Final ===")
    print(f"Sucessos: {results['success']}")
    print(f"Falhas: {results['failed']}")
    print(f"Tempo total: {results['elapsed_seconds']}s")
    print(f"Bytes Originais: {results['original_bytes']}")
    print(f"Bytes Finais: {results['compressed_bytes']}")
    print(f"Cancelado: {results['cancelled']}")