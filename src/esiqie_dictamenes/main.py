import flet as ft

from esiqie_dictamenes.app import App
from esiqie_dictamenes.core.theme import SURFACE, build_theme


def main(page: ft.Page) -> None:
    page.title = "ESIQIE-DICTÁMENES"
    page.theme = build_theme()
    page.bgcolor = SURFACE
    page.padding = 0
    page.render(App)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
