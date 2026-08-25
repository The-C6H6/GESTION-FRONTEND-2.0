import flet as ft

from esiqie_dictamenes.core.theme import TEXT


def page_header(title: str, description: str) -> ft.Control:
    return ft.Column(
        [
            ft.Text(title, size=28, weight=ft.FontWeight.BOLD, color=TEXT),
            ft.Text(description, size=14, color="#5A6478"),
            ft.Divider(height=24),
        ],
        spacing=4,
    )
