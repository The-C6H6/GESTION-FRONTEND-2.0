import flet as ft

from esiqie_dictamenes.core.theme import ESIQIE_BLUE, IPN_WINE


def feedback(message: str, *, error: bool = False) -> ft.Control:
    if not message:
        return ft.Container()
    color = IPN_WINE if error else ESIQIE_BLUE
    return ft.Container(
        content=ft.Text(message, color=color, weight=ft.FontWeight.BOLD),
        bgcolor=f"{color}14",
        border=ft.Border.all(1, color),
        border_radius=8,
        padding=12,
    )
