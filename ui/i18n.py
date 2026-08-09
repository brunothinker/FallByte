from typing import Dict

CURRENT_LANG = "pt"

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "pt": {
        # Geral & App
        "app_title": "FallByte - Media Suite",
        "header_back_tooltip": "Voltar",
        "default_header_title": "FallByte",
        "route_not_found": "Rota '{route_key}' não encontrada.",

        # Home Page
        "home_header_title": "FallByte - Painel Principal",
        "home_mod_image_title": "Módulo de Imagens",
        "home_mod_image_desc": "Conversão, compressão e otimização individual ou em lote.",
        "home_mod_video_title": "Módulo de Vídeos",
        "home_mod_video_desc": "Conversão, corte e compressão de vídeos via FFmpeg.",
        "home_mod_rename_title": "Renomeador em Lote",
        "home_mod_rename_desc": "Organize arquivos com padrões e contadores personalizados.",

        # Image Hubs
        "image_hub_header_title": "Ferramentas de Imagem",
        "image_hub_heading": "Processamento de Imagens",
        "image_hub_subheading": "Selecione a ferramenta que deseja utilizar",
        "image_hub_card_conversion_title": "Conversão de Formato",
        "image_hub_card_conversion_desc": "Altere o formato de suas imagens (PNG, WEBP, JPEG, ICO, TIFF e mais).",
        "image_hub_card_compression_title": "Compressão de Imagem",
        "image_hub_card_compression_desc": "Reduza o peso dos arquivos ajustando a qualidade visual.",

        "conversion_hub_header_title": "Hub de Conversão",
        "conversion_hub_heading": "Conversão de Imagens",
        "conversion_hub_subheading": "Selecione o modo de processamento desejado",
        "conversion_file_card_title": "Arquivo Único",
        "conversion_file_card_desc": "Converta uma imagem individual para qualquer formato suportado.",
        "conversion_dir_card_title": "Diretório em Lote",
        "conversion_dir_card_desc": "Processe uma pasta inteira e converta todas as imagens de uma só vez.",

        "compression_hub_header_title": "Hub de Compressão",
        "compression_hub_heading": "Compressão de Imagens",
        "compression_hub_subheading": "Selecione o modo de processamento desejado",
        "compression_file_card_title": "Arquivo Único",
        "compression_file_card_desc": "Reduza o peso de uma imagem ajustando o percentual de qualidade.",
        "compression_dir_card_title": "Diretório em Lote",
        "compression_dir_card_desc": "Otimize e reduza o peso de todas as imagens de uma pasta.",

        # Form Shared Labels
        "lbl_select_file": "Selecionar Arquivo",
        "lbl_select_input_dir": "Pasta de Origem",
        "lbl_select_output_dir": "Pasta de Destino",
        "lbl_not_selected": "Nenhum selecionado",
        "lbl_target_format": "Formato de Destino",
        "lbl_transparency_color": "Fundo para Transparência (HEX)",
        "lbl_quality": "Qualidade: {quality}%",
        "btn_process": "Iniciar Processamento",
        "msg_success": "Operação concluída com sucesso!",
        "msg_error": "Ocorreu um erro ao processar os arquivos.",
        "msg_select_required": "Selecione os locais de origem e destino para continuar.",

        # Headers de Formulários
        "form_conversion_file_title": "Conversão de Arquivo Único",
        "form_conversion_dir_title": "Conversão de Diretório em Lote",
        "form_compression_file_title": "Compressão de Arquivo Único",
        "form_compression_dir_title": "Compressão de Diretório em Lote",

        # Avisos do Modal de Compressão
        "dialog_incompatible_title": "Formatos Não Comprimíveis",
        "dialog_incompatible_body": "Identificamos {unsupported_count} arquivo(s) não suportados para compressão direta ({sample_exts}).\n\nDica: você pode convertê-los previamente no Módulo de Conversão.\n\nDeseja prosseguir comprimindo apenas os {supported_count} arquivo(s) compatíveis?",
        "btn_cancel": "Cancelar",
        "btn_continue": "Prosseguir Assim Mesmo",
    }
}


def t(key: str, **kwargs) -> str:
    text = TRANSLATIONS.get(CURRENT_LANG, {}).get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text


def set_language(lang_code: str) -> None:
    global CURRENT_LANG
    if lang_code in TRANSLATIONS:
        CURRENT_LANG = lang_code