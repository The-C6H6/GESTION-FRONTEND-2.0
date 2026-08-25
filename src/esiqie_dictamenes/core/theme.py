import flet as ft


ESIQIE_BLUE = "#17338F"
ESIQIE_BLUE_DARK = "#0E225F"
IPN_WINE = "#6C1538"
SURFACE = "#F5F7FB"
TEXT = "#172033"


def build_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=ESIQIE_BLUE,
            secondary=IPN_WINE,
            surface=SURFACE,
        ),
        use_material3=True,
    )
