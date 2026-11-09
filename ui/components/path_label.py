import flet as ft

from ui.i18n import t
from ui.theme import get_color


def create_path_label(initial_text: str | None = None) -> ft.Text:
    """Constructs a standard UI text component for displaying file/directory selection paths.

    Args:
        initial_text (str | None, optional): Custom initial text. Defaults to localized 'lbl_not_selected'.

    Returns:
        ft.Text: Formatted Flet text component for path status rendering.
    """
    return ft.Text(
        initial_text if initial_text is not None else t("lbl_not_selected"),
        size=11,
        color=get_color("subtext"),
        overflow=ft.TextOverflow.ELLIPSIS,
        max_lines=1,
    )