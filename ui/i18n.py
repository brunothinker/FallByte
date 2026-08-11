import logging
from typing import Any, Dict

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
        # Image Hub Navigation Modules
        "image_hub_header_title": "Ferramentas de Imagem",
        "image_hub_heading": "Processamento de Imagens",
        "image_hub_subheading": "Selecione a ferramenta que deseja utilizar",
        "image_hub_card_conversion_title": "Conversão de Formato",
        "image_hub_card_conversion_desc": "Altere o formato de suas imagens (PNG, WEBP, JPEG, ICO, TIFF e mais).",
        "image_hub_card_compression_title": "Compressão de Imagem",
        "image_hub_card_compression_desc": "Reduza o peso dos arquivos ajustando a qualidade visual.",
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
        # Color Options for Transparency Replacement
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
    }
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