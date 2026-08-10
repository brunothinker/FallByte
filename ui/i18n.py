import logging
from typing import Dict, Any

# Setup module logger
logger = logging.getLogger(__name__)

# Active language identifier
CURRENT_LANG: str = "pt"

# Centralized translation dictionary mapping language codes to key-value strings
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "pt": {
        # General & Application Navigation
        "app_title": "FallByte - Media Suite",
        "header_back_tooltip": "Voltar",
        "default_header_title": "FallByte",
        "route_not_found": "Rota '{route_key}' não encontrada.",

        # Home Dashboard
        "home_header_title": "FallByte - Painel Principal",
        "home_mod_image_title": "Módulo de Imagens",
        "home_mod_image_desc": "Conversão, compressão e otimização individual ou em lote.",
        "home_mod_video_title": "Módulo de Vídeos",
        "home_mod_video_desc": "Conversão, corte e compressão de vídeos via FFmpeg.",
        "home_mod_rename_title": "Renomeador em Lote",
        "home_mod_rename_desc": "Organize arquivos com padrões e contadores personalizados.",

        # Image Hub Navigation Modules
        "image_hub_header_title": "Ferramentas de Imagem",
        "image_hub_heading": "Processamento de Imagens",
        "image_hub_subheading": "Selecione a ferramenta que deseja utilizar",
        "image_hub_card_conversion_title": "Conversão de Formato",
        "image_hub_card_conversion_desc": "Altere o formato de suas imagens (PNG, WEBP, JPEG, ICO, TIFF e mais).",
        "image_hub_card_compression_title": "Compressão de Imagem",
        "image_hub_card_compression_desc": "Reduza o peso dos arquivos ajustando a qualidade visual.",

        # Conversion Hub Choices
        "conversion_hub_header_title": "Hub de Conversão",
        "conversion_hub_heading": "Conversão de Imagens",
        "conversion_hub_subheading": "Selecione o modo de processamento desejado",
        "conversion_file_card_title": "Arquivo Único",
        "conversion_file_card_desc": "Converta uma imagem individual para qualquer formato suportado.",
        "conversion_dir_card_title": "Diretório em Lote",
        "conversion_dir_card_desc": "Processe uma pasta inteira e converta todas as imagens de uma só vez.",

        # Compression Hub Choices
        "compression_hub_header_title": "Hub de Compressão",
        "compression_hub_heading": "Compressão de Imagens",
        "compression_hub_subheading": "Selecione o modo de processamento desejado",
        "compression_file_card_title": "Arquivo Único",
        "compression_file_card_desc": "Reduza o peso de uma imagem ajustando o percentual de qualidade.",
        "compression_dir_card_title": "Diretório em Lote",
        "compression_dir_card_desc": "Otimize e reduza o peso de todas as imagens de uma pasta.",

        # Shared Form Labels and Buttons
        "lbl_select_file": "Selecionar Arquivo",
        "lbl_select_input_dir": "Pasta de Origem",
        "lbl_select_output_dir": "Pasta de Destino",
        "lbl_not_selected": "Nenhum selecionado",
        "lbl_target_format": "Formato de Destino",
        "lbl_transparency_color": "Fundo para Transparência",
        "lbl_quality": "Qualidade: {quality}%",
        "btn_process": "Iniciar Processamento",
        "msg_success": "Operação concluída com sucesso!",
        "msg_error": "Ocorreu um erro ao processar os arquivos.",
        "msg_select_required": "Selecione os locais de origem e destino para continuar.",

        # Color Options for Transparency Replacement
        "color_white": "Branco",
        "color_black": "Preto",
        "color_light_gray": "Cinza Claro",
        "color_dark_gray": "Cinza Escuro",
        "color_red": "Vermelho",
        "color_green": "Verde",
        "color_blue": "Azul",
        "color_yellow": "Amarelo",

        # Form Section Headers
        "form_conversion_file_title": "Conversão de Arquivo Único",
        "form_conversion_dir_title": "Conversão de Diretório em Lote",
        "form_compression_file_title": "Compressão de Arquivo Único",
        "form_compression_dir_title": "Compressão de Diretório em Lote",

        # Compression Incompatibility Warning Dialogs
        "dialog_incompatible_title": "Formatos Não Comprimíveis",
        "dialog_incompatible_body": "Identificamos {unsupported_count} arquivo(s) não suportados para compressão direta ({sample_exts}).\n\nDica: você pode convertê-los previamente no Módulo de Conversão.\n\nDeseja prosseguir comprimindo apenas os {supported_count} arquivo(s) compatíveis?",
        "btn_cancel": "Cancelar",
        "btn_continue": "Prosseguir Assim Mesmo",

        # Execution Result and Log Summary Dialog
        "log_dialog_title": "Resultado do Processamento",
        "log_summary_success": "Sucesso",
        "log_summary_failed": "Falhas",
        "log_summary_total": "Total de Arquivos",
        "log_summary_time": "Tempo Decorrido",
        "log_btn_view_logs": "Ver Log Detalhado",
        "log_btn_hide_logs": "Ocultar Log",
        "log_detail_title": "Histórico Detalhado:",
        "log_no_errors": "Nenhum erro registrado durante o processamento.",
    }
}


def t(key: str, **kwargs: Any) -> str:
    """
    Translates a translation key into the active language, replacing dynamic placeholders if provided.

    Args:
        key (str): Key matching a string definition in TRANSLATIONS.
        **kwargs (Any): Dynamic variable assignments used for string formatting.

    Returns:
        str: Translated and formatted text string, or the raw key if no match is found.
    """
    text = TRANSLATIONS.get(CURRENT_LANG, {}).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing placeholder variable {e} when formatting translation key '{key}'.")
    return text


def set_language(lang_code: str) -> None:
    """
    Sets the active language code for the translation helper.

    Args:
        lang_code (str): Language ISO code string (e.g., 'pt', 'en').
    """
    global CURRENT_LANG
    if lang_code in TRANSLATIONS:
        CURRENT_LANG = lang_code
    else:
        logger.warning(f"Attempted to set unsupported language code '{lang_code}'.")