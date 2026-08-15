import logging
from pathlib import Path
from src.video.compression.directory_compression import directory_compressor
from src.video.utils.video_progress import VideoProgressInfo

# Configura o log para exibir os detalhes no console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def handle_progress(progress: VideoProgressInfo) -> None:
    """Função de callback para monitorar o progresso da compressão em tempo real."""
    print(
        f"[{progress.current_file_index}/{progress.total_files}] "
        f"Arquivo: {progress.file_path.name} | "
        f"Sucesso: {progress.success} | "
        f"Orig: {progress.orig_bytes / (1024 * 1024):.2f} MB -> "
        f"Comp: {progress.comp_bytes / (1024 * 1024):.2f} MB | "
        f"Redução: {progress.space_saved_percentage:.1f}% | "
        f"Tempo Decorrido: {progress.elapsed_seconds}s"
    )


if __name__ == "__main__":
    # Caminhos apontando para os mesmos diretórios do teste de conversão
    INPUT_DIR = Path("/home/bhzinn/Vídeos/Teste")
    OUTPUT_DIR = Path("/home/bhzinn/Vídeos/Teste_Compressed")
    QUALITY = 75  # Nível de qualidade desejado (1 a 100)

    print("=== Iniciando Teste de Compressão de Diretório ===")

    # Cria pasta de saída de teste se não existir
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Executa o compressor de diretório
    results = directory_compressor(
        input_dir=INPUT_DIR,
        output_dir=OUTPUT_DIR,
        quality=QUALITY,
        progress_callback=handle_progress,
    )

    print("\n=== Resultado Final ===")
    print(f"Sucessos: {results['success']}")
    print(f"Falhas: {results['failed']}")
    print(f"Tempo total: {results['elapsed_seconds']}s")
    print(f"Bytes Originais: {results['original_bytes']}")
    print(f"Bytes Finais: {results['compressed_bytes']}")
    print(f"Cancelado: {results['cancelled']}")