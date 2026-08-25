import flet as ft


ESIQIE_BLUE = "#17338F"
ESIQIE_BLUE_DARK = "#0E225F"
IPN_WINE = "#6C1538"
SURFACE = "#F5F7FB"
TEXT = "#172033"
ON_PRIMARY = "#FFFFFF"
PRIMARY_CONTAINER = "#E8EDFA"
MUTED_TEXT = "#4D5870"
OUTLINE = "#65718A"


def build_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=ESIQIE_BLUE,
            on_primary=ON_PRIMARY,
            primary_container=PRIMARY_CONTAINER,
            on_primary_container=ESIQIE_BLUE_DARK,
            secondary=IPN_WINE,
            on_secondary=ON_PRIMARY,
            surface=SURFACE,
            on_surface=TEXT,
            on_surface_variant=MUTED_TEXT,
            outline=OUTLINE,
        ),
        button_theme=ft.ButtonTheme(
            style=ft.ButtonStyle(
                bgcolor=ESIQIE_BLUE,
                color=ON_PRIMARY,
            )
        ),
        canvas_color=SURFACE,
        scaffold_bgcolor=SURFACE,
        card_bgcolor=ON_PRIMARY,
        hint_color=MUTED_TEXT,
        use_material3=True,
    )
