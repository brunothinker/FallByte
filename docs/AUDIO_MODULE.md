# Módulo de Áudio — Arquitetura e Escopo (v1)

## 1. Decisões Arquiteturais

### Isolamento de Domínio
* **Desacoplamento total de Vídeo e Imagem:** `src/audio/` não importa nenhum módulo de `src/video/` ou `src/image/`.
* **Engine FFmpeg dedicada (`src/audio/utils/ffmpeg_audio_utils.py`):** Criada separadamente de `ffmpeg_utils.py` (vídeo) para evitar acoplamento com regras de pixel format (`yuv420p`, `10-bit`), filtros de escala (`scale`), tags HEVC (`hvc1`) e estratégias de containers de vídeo.
* **Resolução de binário (`src/audio/utils/binary_manager.py`):** Mantida como duplicata idêntica de `src/video/utils/binary_manager.py` (com o mesmo nome de arquivo por convenção interna para rastreamento de duplicatas até uma futura refatoração centralizada).
* **Reaproveitamento de infraestrutura transversal (`src/utils/`):**
  * `src/utils/file_scanner.py`: Scanner genérico de diretórios por extensão.
  * `src/utils/batch_runner.py`: Orquestração em lote, criação de diretórios de sessão únicos (`create_unique_output_dir`), tracking de bytes originais/comprimidos e limpeza segura em cancelamento (`safe_cleanup_session_files`).
  * `src/utils/progress.py`: Estrutura `ProgressInfo` alimentada em tempo real via `-progress pipe:1` (`duration_seconds`, `processed_seconds`, `speed`).
  * `src/utils/cleanup.py`: Cópia atômica do arquivo original (`copy_original_file_atomically`) quando não há ganho de tamanho ou quando o formato não é recomprimível.

### Escolhas Técnicas de Processamento (FFmpeg)
* **Isolamento da trilha de áudio (`-map 0:a:0 -vn -sn -dn`):** O flag `-vn` descarta capas de álbum embutidas (streams `mjpeg`/`png` muito comuns em `.mp3`, `.m4a` e `.flac`), evitando que o FFmpeg tente transcodificar vídeo ou falhe ao escrever containers puros de áudio.
* **Cadeia de resiliência (2 estratégias):**
  1. *Standard transcode/compression:* Preserva a taxa de amostragem e canais originais (exceto `libopus`, que fixa `-ar 48000` para evitar rejeição de sample rates exóticos).
  2. *Rescue stereo transcode:* Ativa `-fflags +genpts -err_detect ignore_err` e força `-ac 2` (downmix para stereo), recuperando arquivos com headers/timestamps danificados ou entradas multi-canal (5.1/7.1) incompatíveis com encoders como `libmp3lame`.
* **Escrita atômica:** Toda saída FFmpeg escreve primeiro em arquivo temporário oculto (`.<nome>_tmp_<id>.<ext>`) no diretório de destino e só é promovida via `os.replace()` após retorno `0` e tamanho `> 0`.

---

## 2. O que Funciona na v1

### Formatos Suportados
* **Varredura de Entrada (9 formatos):** `.mp3`, `.m4a`, `.aac`, `.ogg`, `.opus`, `.flac`, `.wav`, `.wma`, `.aiff`.
* **Conversão (`audio_file_conversion` / `audio_directory_conversion`):**
  * Converte qualquer um dos 9 formatos de entrada para: `mp3` (`libmp3lame`), `m4a` (`aac`), `opus` (`libopus`), `ogg` (`libvorbis`), `flac` (`flac`), `wav` (`pcm_s16le`).
  * **Bypass inteligente:** Se a extensão de origem já for igual ao formato de destino (ex.: `.mp3` $\rightarrow$ `mp3`) e o arquivo possuir trilha de áudio válida, realiza cópia atômica direta sem perda por re-encoding.
* **Compressão (`audio_file_compression` / `audio_directory_compression`):**
  * **Formatos lossy (`MP3`, `M4A`, `OGG`, `OPUS`):** Mapeia linearmente o slider de qualidade (`1–100`) para faixas de bitrate:
    * `MP3` / `M4A` / `OGG`: `48 kbps` (qualidade 1) até `320 kbps` (qualidade 100).
    * `OPUS`: `32 kbps` (qualidade 1) até `192 kbps` (qualidade 100).
  * **Formatos lossless / não-recomprimíveis (`FLAC`, `WAV`, `AAC`, `WMA`, `AIFF`):** Assim como `GIF`/`BMP`/`HEIC` no módulo de imagem, são aceitos no fluxo e preservados via `copy_original_file_atomically` sem falhar o lote.
  * **Proteção contra crescimento (`keep_original`):** Se o arquivo comprimido resultar em tamanho maior ou igual ao original (`output_size >= original_size`), o arquivo temporário é descartado e o original é mantido intacto no destino.

---

## 3. Limitações Conhecidas e Roadmap Mapeado

| Item | Comportamento Atual (v1) | Evolução Mapeada (Próximas Fases) |
| :--- | :--- | :--- |
| **Múltiplas faixas de áudio** | Processa exclusivamente a primeira faixa de áudio (`-map 0:a:0`). Faixas secundárias (ex.: dublagens alternativas em containers `.mka`/`.ogg`) são ignoradas. | Suporte a listagem e seleção de múltiplas faixas de áudio (`0:a:0`, `0:a:1`, ...), compartilhando a inspeção de streams com o módulo de Vídeo. |
| **Extração de áudio de vídeo** | Fora do escopo da v1 (scanner aceita apenas extensões de áudio puro). | Nova feature dedicada acessível tanto pelo módulo de Vídeo quanto pelo módulo de Áudio, permitindo listar e extrair faixas específicas de arquivos de vídeo. |
| **Áudio multi-canal (5.1 / 7.1)** | A estratégia padrão tenta manter os canais originais; se o encoder rejeitar (ex.: MP3), o fallback faz downmix automático para stereo (`-ac 2`). | Expor controle explícito de canais (Original / Stereo / Mono) na UI e engine para casos de uso como podcasts e voz. |
| **Metadados e capas de álbum** | Metadados globais básicos são copiados pelo FFmpeg, mas capas embutidas são descartadas (`-vn`) para garantir compatibilidade universal. | Preservação seletiva de capas (`attached_pic`) em containers que suportam (MP3 ID3v2 / M4A MP4 atoms). |
| **Camada de UI e Testes** | Apenas `src/` implementado nesta etapa. | Criação dos controllers/páginas Flet (`ui/`), chaves de tradução (`resources/locales/`) e suíte `tests/engine/test_audio_engine.py`. |