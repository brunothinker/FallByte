import flet as ft

from ui.theme import COLOR_TEXT
from ui.utils.compression_utils import validate_quality_value


class QualitySelector(ft.Column):
    """Self-contained UI component encapsulating quality slider and text field synchronization."""

    def __init__(
        self, initial_value: int = 80, label_text: str = "Qualidade da Compressão"
    ) -> None:
        """Initializes quality selector controls and binds bidirectional sync events."""
        self.slider_quality = ft.Slider(
            min=1, max=100, divisions=100, value=initial_value, expand=True
        )

        self.txt_quality = ft.TextField(
            value=str(initial_value),
            width=75,
            height=40,
            text_align=ft.TextAlign.CENTER,
            content_padding=ft.padding.symmetric(vertical=0, horizontal=5),
            suffix_text="%",
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        # Bind internal synchronization handlers
        self.slider_quality.on_change = self._sync_from_slider
        self.txt_quality.on_change = self._sync_from_text
        self.txt_quality.on_blur = self._validate_text_blur

        super().__init__(
            controls=[
                ft.Text(
                    label_text,
                    size=13,
                    color=COLOR_TEXT,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Row(
                    [self.slider_quality, self.txt_quality],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=5,
        )

    def get_value(self) -> int:
        """Returns currently selected quality percentage as validated integer."""
        return validate_quality_value(self.slider_quality.value, default=80)

    def _sync_from_slider(self, e: ft.ControlEvent) -> None:
        """Synchronizes text input field when slider control value changes."""
        if e.control.value is not None:
            q = validate_quality_value(e.control.value)
            self.txt_quality.value = str(q)
            self.txt_quality.update()

    def _sync_from_text(self, e: ft.ControlEvent) -> None:
        """Synchronizes slider control when text input field changes."""
        raw_val = e.control.value.strip() if e.control.value else ""
        if not raw_val:
            return
        try:
            val = int(raw_val)
            if 1 <= val <= 100:
                self.slider_quality.value = val
                self.slider_quality.update()
        except ValueError:
            pass

    def _validate_text_blur(self, e: ft.ControlEvent) -> None:
        """Validates quality input value when text field loses focus."""
        q = validate_quality_value(
            e.control.value, default=int(self.slider_quality.value)
        )
        self.txt_quality.value = str(q)
        self.slider_quality.value = q
        self.txt_quality.update()
        self.slider_quality.update()