import flet as ft

from ui.theme import COLOR_TEXT
from ui.utils.compression_utils import validate_quality_value


class QualitySelector(ft.Column):
    """Self-contained UI component encapsulating quality slider and text field synchronization.

    Provides bidirectional synchronization between an interactive horizontal slider
    and a numeric text input field, ensuring automatic range validation (1-100%)
    and focus-out fallback handling.
    """

    def __init__(
        self, initial_value: int = 80, label_text: str = "Qualidade da Compressão"
    ) -> None:
        """Initializes quality selector controls and binds bidirectional sync events.

        Args:
            initial_value (int, optional): Initial compression quality percentage (1-100).
                Defaults to 80.
            label_text (str, optional): Header title rendered above controls.
                Defaults to "Qualidade da Compressão".
        """
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
        """Returns the currently selected quality percentage as a validated integer.

        Returns:
            int: Validated quality percentage guaranteed to be within 1 and 100.
        """
        slider_val = (
            self.slider_quality.value
            if self.slider_quality.value is not None
            else 80
        )
        return validate_quality_value(slider_val, default=80)

    def _sync_from_slider(self, e: ft.ControlEvent) -> None:
        """Synchronizes text input field when slider control value changes.

        Args:
            e (ft.ControlEvent): Flet event instance emitted on slider movement.
        """
        if e.control.value is not None:
            q = validate_quality_value(e.control.value)
            self.txt_quality.value = str(q)
            self.txt_quality.update()

    def _sync_from_text(self, e: ft.ControlEvent) -> None:
        """Synchronizes slider control when text input field content changes.

        Args:
            e (ft.ControlEvent): Flet event instance emitted on text field typing.
        """
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
        """Validates quality input value and resets boundaries when text field loses focus.

        Args:
            e (ft.ControlEvent): Flet event instance emitted when text field loses focus.
        """
        current_slider_val = int(self.slider_quality.value or 80)
        q = validate_quality_value(
            e.control.value, default=current_slider_val
        )
        self.txt_quality.value = str(q)
        self.slider_quality.value = q
        self.txt_quality.update()
        self.slider_quality.update()