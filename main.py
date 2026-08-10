import flet as ft
from ui.app_layout import create_app_layout
from ui.i18n import t


def main(page: ft.Page):
    page.title = t("app_title")
    page.theme_mode = ft.ThemeMode.DARK

    # Smart system font detection:
    # 'system-ui' instructs the OS to use its default active UI font.
    # Falls back to native sans-serif stack if system-ui fails.
    page.theme = ft.Theme(
        font_family="system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        use_material3=True
    )

    page.window_width = 620
    page.window_height = 800
    page.window_center()

    selected_paths = {}
    page.add(create_app_layout(page, selected_paths))


if __name__ == "__main__":
    ft.app(target=main)