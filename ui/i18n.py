import locale
import logging
from typing import Any

# Setup module logger
logger = logging.getLogger(__name__)

# Active language identifier
CURRENT_LANG: str = "pt"

# Centralized translation dictionary mapping language codes to key-value strings
TRANSLATIONS: dict[str, dict[str, str]] = {
    "pt": {
        # Navigation & Sidebar
        "nav_home": "Inicial",
        "lbl_github_repo": "Repositório GitHub",
        "app_title": "FallByte - Media Suite",
        "header_back_tooltip": "Voltar",
        "route_not_found": "Rota '{route_key}' não encontrada.",
        # Home Dashboard
        "home_header_title": "FallByte - Painel Principal",
        "home_mod_image_title": "Módulo de Imagens",
        "home_mod_image_desc": "Conversão, compressão e otimização individual ou em lote.",
        "home_mod_video_title": "Módulo de Vídeos",
        "home_mod_video_desc": "Conversão e compressão de vídeos mantendo alta qualidade.",
        # Image Hub Navigation Modules
        "image_hub_header_title": "Ferramentas de Imagem",
        "image_hub_heading": "Processamento de Imagens",
        "image_hub_subheading": "Selecione a ferramenta que deseja utilizar",
        "image_hub_card_conversion_title": "Conversão de Formato",
        "image_hub_card_conversion_desc": "Altere o formato das suas imagens individualmente ou em lote.",
        "image_hub_card_compression_title": "Compressão de Imagem",
        "image_hub_card_compression_desc": "Reduza o tamanho dos arquivos ajustando a qualidade visual.",
        # Selector Labels & Popup Items
        "lbl_source": "Origem",
        "lbl_destination": "Destino",
        "lbl_select_file": "Selecionar Arquivo",
        "lbl_select_folder": "Selecionar Pasta",
        "lbl_not_selected": "Nenhum selecionado",
        "lbl_quality_title": "Qualidade da Compressão",
        "lbl_target_format": "Formato de Destino",
        "lbl_transparency_color": "Fundo para Transparência",
        "lbl_no_extension": "Sem extensão",
        "lbl_language": "Idioma",
        # Themes i18n
        "lbl_theme": "Tema do App",
        "lbl_select_theme": "Selecionar Tema",
        "theme_section_dark": "Temas Escuros (Dark)",
        "theme_section_light": "Temas Claros (Light)",
        "theme_blue_dark": "Azul",
        "theme_purple_dark": "Roxo",
        "theme_emerald_dark": "Esmeralda",
        "theme_red_dark": "Vermelho",
        "theme_amber_dark": "Âmbar",
        "theme_blue_light": "Azul",
        "theme_purple_light": "Roxo",
        "theme_emerald_light": "Esmeralda",
        "theme_red_light": "Vermelho",
        "theme_amber_light": "Âmbar",
        # Color Options
        "color_white": "Branco",
        "color_black": "Preto",
        "color_light_gray": "Cinza Claro",
        "color_dark_gray": "Cinza Escuro",
        "color_red": "Vermelho",
        "color_green": "Verde",
        "color_blue": "Azul",
        "color_yellow": "Amarelo",
        # Action Buttons & Status Messages
        "btn_process": "Iniciar Processamento",
        "btn_stop_process": "PARAR PROCESSAMENTO",
        "btn_ok": "OK",
        "btn_cancel": "Cancelar",
        "btn_continue": "Prosseguir Assim Mesmo",
        "btn_keep_running": "Não, Continuar",
        "btn_stop_and_delete": "Sim, Interromper e Apagar",
        "btn_copy_log": "Copiar Log",
        "msg_log_copied": "Log copiado para a área de transferência!",
        "msg_processing": "Processando...",
        "msg_success": "Operação concluída com sucesso!",
        "msg_error": "Ocorreu um erro ao processar os arquivos.",
        "msg_select_required": "Selecione os locais de origem e destino para continuar.",
        "msg_cancelling": "Cancelando e limpando arquivos gerados...",
        "msg_converting_progress": "Convertendo: [{current}/{total}] - {filename}",
        "msg_compressing_progress": "Comprimindo: [{current}/{total}] - {filename}",
        "msg_process_cancelled": "Processamento cancelado. {count} arquivo(s) gerado(s) foram apagados.",
        "msg_success_summary": "{msg} | Sucesso: {successful} / {total}",
        # Dialog Messages
        "dialog_incompatible_title": "Formatos Não Comprimíveis",
        "dialog_incompatible_body": "Identificamos {unsupported_count} arquivo(s) não suportados para compressão direta ({sample_exts}).\n\nDica: você pode convertê-los previamente no Módulo de Conversão.\n\nDeseja prosseguir comprimindo apenas os {supported_count} arquivo(s) compatíveis?",
        "dialog_cancel_title": "Confirmar Cancelamento",
        "dialog_cancel_body": "Deseja realmente interromper o processamento?\nOs arquivos salvos nesta sessão no destino serão apagados.",
        # Summary & Log Dialog
        "log_dialog_title": "Resultado do Processamento",
        "log_summary_success": "Sucesso",
        "log_summary_failed": "Falhas",
        "log_summary_total": "Total de Arquivos",
        "log_summary_time": "Tempo Decorrido",
        "log_btn_view_logs": "Ver Log Detalhado",
        "log_btn_hide_logs": "Ocultar Log",
        "log_detail_title": "Histórico Detalhado:",
        "log_no_errors": "Nenhum erro registrado durante o processamento.",
        "log_size_stat": "Tamanho: {orig} -> {comp}",
        "log_reduction_stat": "Redução: -{pct:.1f}%",
        # Video Hub Navigation Modules
        "video_hub_header_title": "Ferramentas de Vídeo",
        "video_hub_heading": "Processamento de Vídeos",
        "video_hub_subheading": "Selecione a ferramenta que deseja utilizar",
        "video_hub_card_conversion_title": "Conversão de Vídeo",
        "video_hub_card_conversion_desc": "Altere o formato dos seus vídeos mantendo a compatibilidade.",
        "video_hub_card_compression_title": "Compressão de Vídeo",
        "video_hub_card_compression_desc": "Reduza o peso dos arquivos de vídeo preservando a qualidade.",
        "lbl_quality_percentage": "Qualidade: {value}%",
        "msg_uncompressible_notice": "Nota: Formatos brutos ou especiais ({formats}) não suportam compressão direta e serão mantidos intactos.",
        "msg_supported_formats_notice": "Formatos suportados para compressão: {formats}",
    },
    "en": {
        # Navigation & Sidebar
        "nav_home": "Home",
        "lbl_github_repo": "GitHub Repository",
        "app_title": "FallByte - Media Suite",
        "header_back_tooltip": "Back",
        "route_not_found": "Route '{route_key}' not found.",
        # Home Dashboard
        "home_header_title": "FallByte - Main Dashboard",
        "home_mod_image_title": "Image Module",
        "home_mod_image_desc": "Single or batch image conversion, compression, and optimization.",
        "home_mod_video_title": "Video Module",
        "home_mod_video_desc": "Video conversion and compression while maintaining high quality.",
        # Image Hub Navigation Modules
        "image_hub_header_title": "Image Tools",
        "image_hub_heading": "Image Processing",
        "image_hub_subheading": "Select the tool you want to use",
        "image_hub_card_conversion_title": "Format Conversion",
        "image_hub_card_conversion_desc": "Change the format of your images individually or in batch.",
        "image_hub_card_compression_title": "Image Compression",
        "image_hub_card_compression_desc": "Reduce file size by adjusting visual quality.",
        # Selector Labels & Popup Items
        "lbl_source": "Source",
        "lbl_destination": "Destination",
        "lbl_select_file": "Select File",
        "lbl_select_folder": "Select Folder",
        "lbl_not_selected": "None selected",
        "lbl_quality_title": "Compression Quality",
        "lbl_target_format": "Target Format",
        "lbl_transparency_color": "Transparency Background",
        "lbl_no_extension": "No extension",
        "lbl_language": "Language",
        # Themes i18n
        "lbl_theme": "App Theme",
        "lbl_select_theme": "Select Theme",
        "theme_section_dark": "Dark Themes",
        "theme_section_light": "Light Themes",
        "theme_blue_dark": "Blue",
        "theme_purple_dark": "Purple",
        "theme_emerald_dark": "Emerald",
        "theme_red_dark": "Red",
        "theme_amber_dark": "Amber",
        "theme_blue_light": "Blue",
        "theme_purple_light": "Purple",
        "theme_emerald_light": "Emerald",
        "theme_red_light": "Red",
        "theme_amber_light": "Amber",
        # Color Options
        "color_white": "White",
        "color_black": "Black",
        "color_light_gray": "Light Gray",
        "color_dark_gray": "Dark Gray",
        "color_red": "Red",
        "color_green": "Green",
        "color_blue": "Blue",
        "color_yellow": "Yellow",
        # Action Buttons & Status Messages
        "btn_process": "Start Processing",
        "btn_stop_process": "STOP PROCESSING",
        "btn_ok": "OK",
        "btn_cancel": "Cancel",
        "btn_continue": "Proceed Anyway",
        "btn_keep_running": "No, Keep Running",
        "btn_stop_and_delete": "Yes, Stop and Delete",
        "btn_copy_log": "Copy Log",
        "msg_log_copied": "Log copied to clipboard!",
        "msg_processing": "Processing...",
        "msg_success": "Operation completed successfully!",
        "msg_error": "An error occurred while processing the files.",
        "msg_select_required": "Please select source and destination locations to continue.",
        "msg_cancelling": "Cancelling and cleaning generated files...",
        "msg_converting_progress": "Converting: [{current}/{total}] - {filename}",
        "msg_compressing_progress": "Compressing: [{current}/{total}] - {filename}",
        "msg_process_cancelled": "Processing cancelled. {count} generated file(s) were deleted.",
        "msg_success_summary": "{msg} | Success: {successful} / {total}",
        # Dialog Messages
        "dialog_incompatible_title": "Uncompressible Formats",
        "dialog_incompatible_body": "We found {unsupported_count} file(s) not supported for direct compression ({sample_exts}).\n\nTip: You can convert them beforehand using the Conversion Module.\n\nDo you want to proceed compressing only the {supported_count} compatible file(s)?",
        "dialog_cancel_title": "Confirm Cancellation",
        "dialog_cancel_body": "Do you really want to stop processing?\nFiles saved in the destination directory during this session will be deleted.",
        # Summary & Log Dialog
        "log_dialog_title": "Processing Results",
        "log_summary_success": "Success",
        "log_summary_failed": "Failed",
        "log_summary_total": "Total Files",
        "log_summary_time": "Elapsed Time",
        "log_btn_view_logs": "View Detailed Log",
        "log_btn_hide_logs": "Hide Log",
        "log_detail_title": "Detailed History:",
        "log_no_errors": "No errors recorded during processing.",
        "log_size_stat": "Size: {orig} -> {comp}",
        "log_reduction_stat": "Reduction: -{pct:.1f}%",
        # Video Hub Navigation Modules
        "video_hub_header_title": "Video Tools",
        "video_hub_heading": "Video Processing",
        "video_hub_subheading": "Select the tool you want to use",
        "video_hub_card_conversion_title": "Video Conversion",
        "video_hub_card_conversion_desc": "Change video formats while maintaining compatibility.",
        "video_hub_card_compression_title": "Video Compression",
        "video_hub_card_compression_desc": "Reduce video file sizes while preserving quality.",
        "lbl_quality_percentage": "Quality: {value}%",
        "msg_uncompressible_notice": "Note: Raw or special formats ({formats}) do not support direct compression and will be kept intact.",
        "msg_supported_formats_notice": "Supported formats for compression: {formats}",
    },
    "es": {
        # Navigation & Sidebar
        "nav_home": "Inicio",
        "lbl_github_repo": "Repositorio GitHub",
        "app_title": "FallByte - Media Suite",
        "header_back_tooltip": "Volver",
        "route_not_found": "Ruta '{route_key}' no encontrada.",
        # Home Dashboard
        "home_header_title": "FallByte - Panel Principal",
        "home_mod_image_title": "Módulo de Imágenes",
        "home_mod_image_desc": "Conversión, compresión y optimización individual o en lote.",
        "home_mod_video_title": "Módulo de Videos",
        "home_mod_video_desc": "Conversión y compresión de videos manteniendo alta calidad.",
        # Image Hub Navigation Modules
        "image_hub_header_title": "Herramientas de Imagen",
        "image_hub_heading": "Procesamiento de Imágenes",
        "image_hub_subheading": "Seleccione la herramienta que desea utilizar",
        "image_hub_card_conversion_title": "Conversión de Formato",
        "image_hub_card_conversion_desc": "Cambie el formato de sus imágenes de forma individual o en lote.",
        "image_hub_card_compression_title": "Compresión de Imagen",
        "image_hub_card_compression_desc": "Reduzca el tamaño de los archivos ajustando la calidad visual.",
        # Selector Labels & Popup Items
        "lbl_source": "Origen",
        "lbl_destination": "Destino",
        "lbl_select_file": "Seleccionar Archivo",
        "lbl_select_folder": "Seleccionar Carpeta",
        "lbl_not_selected": "Ninguno seleccionado",
        "lbl_quality_title": "Calidad de Compresión",
        "lbl_target_format": "Formato de Destino",
        "lbl_transparency_color": "Fondo para Transparencia",
        "lbl_no_extension": "Sin extensión",
        "lbl_language": "Idioma",
        # Themes i18n
        "lbl_theme": "Tema de la Aplicación",
        "lbl_select_theme": "Seleccionar Tema",
        "theme_section_dark": "Temas Oscuros (Dark)",
        "theme_section_light": "Temas Claros (Light)",
        "theme_blue_dark": "Azul",
        "theme_purple_dark": "Púrpura",
        "theme_emerald_dark": "Esmeralda",
        "theme_red_dark": "Rojo",
        "theme_amber_dark": "Ámbar",
        "theme_blue_light": "Azul",
        "theme_purple_light": "Púrpura",
        "theme_emerald_light": "Esmeralda",
        "theme_red_light": "Rojo",
        "theme_amber_light": "Ámbar",
        # Color Options
        "color_white": "Blanco",
        "color_black": "Negro",
        "color_light_gray": "Gris Claro",
        "color_dark_gray": "Gris Oscuro",
        "color_red": "Rojo",
        "color_green": "Verde",
        "color_blue": "Azul",
        "color_yellow": "Amarillo",
        # Action Buttons & Status Messages
        "btn_process": "Iniciar Procesamiento",
        "btn_stop_process": "DETENER PROCESAMIENTO",
        "btn_ok": "Aceptar",
        "btn_cancel": "Cancelar",
        "btn_continue": "Continuar De Todos Modos",
        "btn_keep_running": "No, Continuar",
        "btn_stop_and_delete": "Sí, Interrumpir y Eliminar",
        "btn_copy_log": "Copiar Registro",
        "msg_log_copied": "¡Registro copiado al portapapeles!",
        "msg_processing": "Procesando...",
        "msg_success": "¡Operación completada con éxito!",
        "msg_error": "Ocurrió un error al procesar los archivos.",
        "msg_select_required": "Seleccione la ubicación de origen y destino para continuar.",
        "msg_cancelling": "Cancelando y limpiando archivos generados...",
        "msg_converting_progress": "Convirtiendo: [{current}/{total}] - {filename}",
        "msg_compressing_progress": "Comprimiendo: [{current}/{total}] - {filename}",
        "msg_process_cancelled": "Procesamiento cancelado. Se eliminaron {count} archivo(s) generado(s).",
        "msg_success_summary": "{msg} | Éxito: {successful} / {total}",
        # Dialog Messages
        "dialog_incompatible_title": "Formatos No Comprimibles",
        "dialog_incompatible_body": "Identificamos {unsupported_count} archivo(s) no compatibles con compresión directa ({sample_exts}).\n\nConsejo: puede convertirlos previamente en el Módulo de Conversión.\n\n¿Desea continuar comprimiendo solo los {supported_count} archivo(s) compatibles?",
        "dialog_cancel_title": "Confirmar Cancelación",
        "dialog_cancel_body": "¿Realmente desea detener el procesamiento?\nLos archivos guardados en el destino durante esta sesión serán eliminados.",
        # Summary & Log Dialog
        "log_dialog_title": "Resultado del Procesamiento",
        "log_summary_success": "Éxito",
        "log_summary_failed": "Fallos",
        "log_summary_total": "Total de Archivos",
        "log_summary_time": "Tiempo Transcurrido",
        "log_btn_view_logs": "Ver Registro Detallado",
        "log_btn_hide_logs": "Ocultar Registro",
        "log_detail_title": "Historial Detallado:",
        "log_no_errors": "No se registraron errores durante el procesamiento.",
        "log_size_stat": "Tamaño: {orig} -> {comp}",
        "log_reduction_stat": "Reducción: -{pct:.1f}%",
        # Video Hub Navigation Modules
        "video_hub_header_title": "Herramientas de Video",
        "video_hub_heading": "Procesamiento de Videos",
        "video_hub_subheading": "Seleccione la herramienta que desea utilizar",
        "video_hub_card_conversion_title": "Conversión de Video",
        "video_hub_card_conversion_desc": "Cambie el formato de sus videos manteniendo la compatibilidad.",
        "video_hub_card_compression_title": "Compresión de Video",
        "video_hub_card_compression_desc": "Reduzca el tamaño de los archivos de video preservando la calidad.",
        "lbl_quality_percentage": "Calidad: {value}%",
        "msg_uncompressible_notice": "Nota: Los formatos brutos o especiales ({formats}) no admiten compresión directa y se mantendrán intactos.",
        "msg_supported_formats_notice": "Formatos compatibles para compresión: {formats}",
    },
}

# Display names for the language selector UI
AVAILABLE_LANGUAGES: dict[str, str] = {
    "pt": "🇧🇷 Português",
    "en": "🇺🇸 English",
    "es": "🇪🇸 Español",
}


def t(key: str, **kwargs: Any) -> str:
    """Translates a key into active language, replacing dynamic placeholders."""
    text = TRANSLATIONS.get(CURRENT_LANG, {}).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError as e:
            logger.warning(
                f"Missing placeholder variable {e} when formatting translation key '{key}'."
            )
    return text


def set_language(lang_code: str) -> None:
    """Sets active language code for translation helper."""
    global CURRENT_LANG
    if lang_code in TRANSLATIONS:
        CURRENT_LANG = lang_code
    else:
        logger.warning(
            f"Attempted to set unsupported language code '{lang_code}'."
        )


def detect_system_language() -> str:
    """Detects system language code using locale module, falling back to 'pt'."""
    try:
        sys_locale, _ = locale.getdefaultlocale()
        if sys_locale:
            lang_prefix = sys_locale.split("_")[0].lower()
            if lang_prefix in TRANSLATIONS:
                return lang_prefix
    except (AttributeError, ValueError, locale.Error) as e:
        logger.warning(f"Failed to detect system locale: {e}")
    return "pt"